/*
 * Concurrent Banking Transaction System
 * CS-2006 Operating Systems | Spring 2026
 * Instructor: Dr. Ghufran Ahmed
 *
 * Group Members:
 *   Muhammad Zain Khan    (24K-0838)
 *   Muhammad Atta Hussain (24K-0797)
 *   Muhammad Zamin        (24K-0982)
 *
 * Compile: gcc -o banking banking.c -lpthread -lm
 * Run:     ./banking
 *
 * Admin password : fast
 * Account PINs   : ID * 1111  (e.g. acc-1 PIN=1111, acc-2 PIN=2222 ...)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <semaphore.h>
#include <unistd.h>
#include <time.h>
#include <stdarg.h>
#include <math.h>

#define MAX_ACCOUNTS        10
#define MAX_TRANSACTIONS    2000
#define MAX_CONCURRENT_TXN  4
#define FRAUD_THRESHOLD     8000.0
#define SIM_CLIENTS         8
#define SIM_VIP             2
#define SIM_OPS             7
#define ADMIN_PASSWORD      "fast"
#define PIN_MAX_ATTEMPTS    3

typedef enum { TXN_DEPOSIT = 0, TXN_WITHDRAW, TXN_TRANSFER } TxnType;

typedef enum {
    TXN_SUCCESS = 0,
    TXN_FAIL_FUNDS,
    TXN_FAIL_FROZEN,
    TXN_FAIL_FRAUD,
    TXN_ROLLED_BACK
} TxnStatus;

typedef struct {
    int       id;
    TxnType   type;
    TxnStatus status;
    int       src_acc;
    int       dst_acc;
    double    amount;
    double    balance_after;
    time_t    timestamp;
    int       thread_id;
    int       is_vip;
} Transaction;

typedef struct {
    int             id;
    char            owner[32];
    char            pin[8];
    double          balance;
    int             is_vip;
    int             frozen;
    pthread_mutex_t lock;
} Account;

typedef struct {
    Account         accounts[MAX_ACCOUNTS];
    int             num_accounts;
    Transaction     log[MAX_TRANSACTIONS];
    int             log_count;
    pthread_mutex_t log_mutex;
    pthread_mutex_t console_mutex;
    sem_t           txn_sem;
    double          initial_total;
    double          total_deposited;
    double          total_withdrawn;
    int             live_feed;
} Bank;

typedef struct {
    Bank *bank;
    int   thread_id;
    int   is_vip;
    int   num_ops;
} ThreadArg;

static int txn_deposit (Bank*, int, double, int, int);
static int txn_withdraw(Bank*, int, double, int, int);
static int txn_transfer(Bank*, int, int, double, int, int);

/* Thread-safe print used during simulation */
static void blog(Bank *b, const char *fmt, ...)
{
    if (!b->live_feed) return;
    pthread_mutex_lock(&b->console_mutex);
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
    pthread_mutex_unlock(&b->console_mutex);
}

static const char *type_str(TxnType t)
{
    switch (t) {
        case TXN_DEPOSIT:  return "DEPOSIT ";
        case TXN_WITHDRAW: return "WITHDRAW";
        case TXN_TRANSFER: return "TRANSFER";
        default:           return "UNKNOWN ";
    }
}

static const char *status_str(TxnStatus s)
{
    switch (s) {
        case TXN_SUCCESS:     return "SUCCESS     ";
        case TXN_FAIL_FUNDS:  return "INSUFFICIENT";
        case TXN_FAIL_FROZEN: return "FROZEN      ";
        case TXN_FAIL_FRAUD:  return "FRAUD-BLOCK ";
        case TXN_ROLLED_BACK: return "ROLLED BACK ";
        default:              return "UNKNOWN     ";
    }
}

static void clear_screen(void) { printf("\033[2J\033[H"); }

static void press_enter(void)
{
    printf("\n  Press ENTER to continue...");
    while (getchar() != '\n');
}

/* Read input without echoing to terminal */
static void read_hidden(const char *prompt, char *buf, int maxlen)
{
    printf("%s", prompt);
    fflush(stdout);
    system("stty -echo 2>/dev/null");
    if (fgets(buf, maxlen, stdin))
        buf[strcspn(buf, "\n")] = '\0';
    system("stty echo 2>/dev/null");
    printf("\n");
}

static int check_admin_password(void)
{
    char pwd[64];
    int attempts = 3;
    while (attempts--) {
        read_hidden("  Admin password: ", pwd, sizeof(pwd));
        if (strcmp(pwd, ADMIN_PASSWORD) == 0) return 1;
        printf("  Wrong password. %d attempt(s) left.\n", attempts);
    }
    printf("  Access denied.\n");
    return 0;
}

static int check_pin(Bank *b, int acc_id)
{
    Account *a = &b->accounts[acc_id];
    char entered[16];
    int attempts = PIN_MAX_ATTEMPTS;

    printf("  Account: %s\n", a->owner);
    while (attempts--) {
        read_hidden("  Enter PIN: ", entered, sizeof(entered));
        if (strcmp(entered, a->pin) == 0) return 1;
        printf("  Wrong PIN. %d attempt(s) left.\n", attempts);
    }

    pthread_mutex_lock(&a->lock);
    a->frozen = 1;
    pthread_mutex_unlock(&a->lock);
    printf("  Too many wrong attempts. Account FROZEN.\n");
    press_enter();
    return 0;
}

static void bank_init(Bank *b)
{
    memset(b, 0, sizeof(*b));
    pthread_mutex_init(&b->log_mutex,     NULL);
    pthread_mutex_init(&b->console_mutex, NULL);
    sem_init(&b->txn_sem, 0, MAX_CONCURRENT_TXN);
    b->live_feed = 1;
}

static void bank_add_account(Bank *b, int id, const char *owner,
                              const char *pin, double balance, int is_vip)
{
    if (b->num_accounts >= MAX_ACCOUNTS) return;
    Account *a = &b->accounts[b->num_accounts++];
    a->id      = id;
    a->balance = balance;
    a->is_vip  = is_vip;
    a->frozen  = 0;
    strncpy(a->owner, owner, sizeof(a->owner) - 1);
    strncpy(a->pin,   pin,   sizeof(a->pin)   - 1);
    pthread_mutex_init(&a->lock, NULL);
    b->initial_total += balance;
}

static void bank_destroy(Bank *b)
{
    for (int i = 0; i < b->num_accounts; i++)
        pthread_mutex_destroy(&b->accounts[i].lock);
    pthread_mutex_destroy(&b->log_mutex);
    pthread_mutex_destroy(&b->console_mutex);
    sem_destroy(&b->txn_sem);
}

static int fraud_check(Bank *b, int acc_id, double amount, TxnType type)
{
    (void)type;
    if (amount > FRAUD_THRESHOLD) {
        if (b->live_feed) {
            pthread_mutex_lock(&b->console_mutex);
            printf("  [FRAUD] acc-%d: Rs.%.2f exceeds limit -> ACCOUNT FROZEN\n",
                   acc_id + 1, amount);
            pthread_mutex_unlock(&b->console_mutex);
        }
        pthread_mutex_lock(&b->accounts[acc_id].lock);
        b->accounts[acc_id].frozen = 1;
        pthread_mutex_unlock(&b->accounts[acc_id].lock);
        return 1;
    }
    pthread_mutex_lock(&b->accounts[acc_id].lock);
    int frozen = b->accounts[acc_id].frozen;
    pthread_mutex_unlock(&b->accounts[acc_id].lock);
    if (frozen) {
        if (b->live_feed) {
            pthread_mutex_lock(&b->console_mutex);
            printf("  [FRAUD] acc-%d is FROZEN\n", acc_id + 1);
            pthread_mutex_unlock(&b->console_mutex);
        }
        return 1;
    }
    return 0;
}

static void record(Bank *b, TxnType type, TxnStatus status,
                   int src, int dst, double amount,
                   double bal_after, int tid, int vip)
{
    pthread_mutex_lock(&b->log_mutex);
    if (b->log_count < MAX_TRANSACTIONS) {
        Transaction *t   = &b->log[b->log_count++];
        t->id            = b->log_count;
        t->type          = type;
        t->status        = status;
        t->src_acc       = src;
        t->dst_acc       = dst;
        t->amount        = amount;
        t->balance_after = bal_after;
        t->timestamp     = time(NULL);
        t->thread_id     = tid;
        t->is_vip        = vip;
    }
    pthread_mutex_unlock(&b->log_mutex);
}

static int txn_deposit(Bank *b, int acc_id, double amount, int tid, int vip)
{
    if (acc_id < 0 || acc_id >= b->num_accounts || amount <= 0) return -1;

    if (fraud_check(b, acc_id, amount, TXN_DEPOSIT)) {
        record(b, TXN_DEPOSIT, TXN_FAIL_FRAUD, acc_id+1, -1, amount, -1, tid, vip);
        return -1;
    }

    sem_wait(&b->txn_sem);

    Account *a = &b->accounts[acc_id];
    pthread_mutex_lock(&a->lock);

    if (a->frozen) {
        double bal = a->balance;
        pthread_mutex_unlock(&a->lock);
        sem_post(&b->txn_sem);
        record(b, TXN_DEPOSIT, TXN_FAIL_FROZEN, acc_id+1, -1, amount, bal, tid, vip);
        blog(b, "  [T%-2d]%s DEPOSIT  acc-%-2d +%-9.2f BLOCKED(frozen)",
             tid, vip ? "[VIP]" : "     ", acc_id+1, amount);
        return -1;
    }

    a->balance += amount;
    double bal = a->balance;
    pthread_mutex_unlock(&a->lock);

    pthread_mutex_lock(&b->log_mutex);
    b->total_deposited += amount;
    pthread_mutex_unlock(&b->log_mutex);

    sem_post(&b->txn_sem);

    record(b, TXN_DEPOSIT, TXN_SUCCESS, acc_id+1, -1, amount, bal, tid, vip);
    blog(b, "  [T%-2d]%s DEPOSIT  acc-%-2d +%-9.2f bal=%.2f",
         tid, vip ? "[VIP]" : "     ", acc_id+1, amount, bal);
    return 0;
}

static int txn_withdraw(Bank *b, int acc_id, double amount, int tid, int vip)
{
    if (acc_id < 0 || acc_id >= b->num_accounts || amount <= 0) return -1;

    if (fraud_check(b, acc_id, amount, TXN_WITHDRAW)) {
        record(b, TXN_WITHDRAW, TXN_FAIL_FRAUD, acc_id+1, -1, amount, -1, tid, vip);
        return -1;
    }

    sem_wait(&b->txn_sem);

    Account *a = &b->accounts[acc_id];
    pthread_mutex_lock(&a->lock);

    if (a->frozen) {
        double bal = a->balance;
        pthread_mutex_unlock(&a->lock);
        sem_post(&b->txn_sem);
        record(b, TXN_WITHDRAW, TXN_FAIL_FROZEN, acc_id+1, -1, amount, bal, tid, vip);
        blog(b, "  [T%-2d]%s WITHDRAW acc-%-2d -%-9.2f BLOCKED(frozen)",
             tid, vip ? "[VIP]" : "     ", acc_id+1, amount);
        return -1;
    }

    if (a->balance < amount) {
        double bal = a->balance;
        pthread_mutex_unlock(&a->lock);
        sem_post(&b->txn_sem);
        record(b, TXN_WITHDRAW, TXN_FAIL_FUNDS, acc_id+1, -1, amount, bal, tid, vip);
        blog(b, "  [T%-2d]%s WITHDRAW acc-%-2d -%-9.2f INSUFFICIENT(bal=%.2f)",
             tid, vip ? "[VIP]" : "     ", acc_id+1, amount, bal);
        return -1;
    }

    a->balance -= amount;
    double bal = a->balance;
    pthread_mutex_unlock(&a->lock);

    pthread_mutex_lock(&b->log_mutex);
    b->total_withdrawn += amount;
    pthread_mutex_unlock(&b->log_mutex);

    sem_post(&b->txn_sem);

    record(b, TXN_WITHDRAW, TXN_SUCCESS, acc_id+1, -1, amount, bal, tid, vip);
    blog(b, "  [T%-2d]%s WITHDRAW acc-%-2d -%-9.2f bal=%.2f",
         tid, vip ? "[VIP]" : "     ", acc_id+1, amount, bal);
    return 0;
}

static int txn_transfer(Bank *b, int src, int dst, double amount, int tid, int vip)
{
    if (src < 0 || src >= b->num_accounts) return -1;
    if (dst < 0 || dst >= b->num_accounts) return -1;
    if (src == dst || amount <= 0)          return -1;

    if (fraud_check(b, src, amount, TXN_TRANSFER)) {
        record(b, TXN_TRANSFER, TXN_FAIL_FRAUD, src+1, dst+1, amount, -1, tid, vip);
        return -1;
    }

    sem_wait(&b->txn_sem);

    /* Deadlock prevention: always lock lower index first */
    Account *first  = (src < dst) ? &b->accounts[src] : &b->accounts[dst];
    Account *second = (src < dst) ? &b->accounts[dst] : &b->accounts[src];
    pthread_mutex_lock(&first->lock);
    pthread_mutex_lock(&second->lock);

    Account *a_src = &b->accounts[src];
    Account *a_dst = &b->accounts[dst];

    if (a_src->frozen || a_dst->frozen) {
        pthread_mutex_unlock(&second->lock);
        pthread_mutex_unlock(&first->lock);
        sem_post(&b->txn_sem);
        record(b, TXN_TRANSFER, TXN_FAIL_FROZEN, src+1, dst+1, amount, a_src->balance, tid, vip);
        blog(b, "  [T%-2d]%s TRANSFER acc-%-2d->%-2d Rs.%-8.2f FROZEN",
             tid, vip ? "[VIP]" : "     ", src+1, dst+1, amount);
        return -1;
    }

    if (a_src->balance < amount) {
        double bal = a_src->balance;
        pthread_mutex_unlock(&second->lock);
        pthread_mutex_unlock(&first->lock);
        sem_post(&b->txn_sem);
        record(b, TXN_TRANSFER, TXN_FAIL_FUNDS, src+1, dst+1, amount, bal, tid, vip);
        blog(b, "  [T%-2d]%s TRANSFER acc-%-2d->%-2d Rs.%-8.2f INSUFFICIENT(%.2f)",
             tid, vip ? "[VIP]" : "     ", src+1, dst+1, amount, bal);
        return -1;
    }

    a_src->balance -= amount;
    a_dst->balance += amount;
    double src_bal = a_src->balance;
    pthread_mutex_unlock(&second->lock);
    pthread_mutex_unlock(&first->lock);
    sem_post(&b->txn_sem);

    record(b, TXN_TRANSFER, TXN_SUCCESS, src+1, dst+1, amount, src_bal, tid, vip);
    blog(b, "  [T%-2d]%s TRANSFER acc-%-2d->%-2d Rs.%-8.2f src_bal=%.2f",
         tid, vip ? "[VIP]" : "     ", src+1, dst+1, amount, src_bal);
    return 0;
}

static void print_banner(void)
{
    printf(
"  +==============================================================+\n"
"  |       CONCURRENT BANKING TRANSACTION SYSTEM                 |\n"
"  |       CS-2006 Operating Systems  |  Spring 2026             |\n"
"  |       Instructor: Dr. Ghufran Ahmed                         |\n"
"  +--------------------------------------------------------------+\n"
"  |  Zain Khan (24K-0838)  .  Atta Hussain (24K-0797)           |\n"
"  |  Muhammad Zamin (24K-0982)                                  |\n"
"  +==============================================================+\n\n");
}

static void print_accounts(Bank *b)
{
    printf(
"  +----+----------------------+--------------+--------+\n"
"  | ID | Owner                |   Balance    |  Type  |\n"
"  +----+----------------------+--------------+--------+\n");

    for (int i = 0; i < b->num_accounts; i++) {
        Account *a = &b->accounts[i];
        const char *label;
        if (a->frozen)      label = "FROZEN";
        else if (a->is_vip) label = "VIP   ";
        else                label = "STD   ";
        printf("  | %-2d | %-20s | Rs.%9.2f | %s |\n",
               a->id, a->owner, a->balance, label);
    }

    printf("  +----+----------------------+--------------+--------+\n");

    double total = 0;
    for (int i = 0; i < b->num_accounts; i++) total += b->accounts[i].balance;
    printf("  System total: Rs.%.2f\n", total);
}

static void print_log_tail(Bank *b, int last_n)
{
    int start = b->log_count - last_n;
    if (start < 0) start = 0;

    printf(
"  +-----+------+----------+-----+-----+------------+--------------+----------------+\n"
"  |  #  |  T   |  Type    | Src | Dst |   Amount   |  Bal After   | Status         |\n"
"  +-----+------+----------+-----+-----+------------+--------------+----------------+\n");

    for (int i = start; i < b->log_count; i++) {
        Transaction *t = &b->log[i];
        char dst_s[8], bal_s[14];
        if (t->dst_acc == -1) snprintf(dst_s, sizeof(dst_s), "  - ");
        else                   snprintf(dst_s, sizeof(dst_s), " %-3d", t->dst_acc);
        if (t->balance_after < 0)
             snprintf(bal_s, sizeof(bal_s), "     -      ");
        else snprintf(bal_s, sizeof(bal_s), "Rs.%9.2f", t->balance_after);

        printf("  | %3d | T%-3d | %s | %-3d |%s  | Rs.%8.2f | %s | %s |\n",
               t->id, t->thread_id, type_str(t->type),
               t->src_acc, dst_s, t->amount, bal_s, status_str(t->status));
    }
    printf(
"  +-----+------+----------+-----+-----+------------+--------------+----------------+\n");
    printf("  Showing %d of %d transactions.\n", b->log_count - start, b->log_count);
}

static void print_consistency(Bank *b)
{
    double total    = 0.0;
    for (int i = 0; i < b->num_accounts; i++) total += b->accounts[i].balance;
    double expected = b->initial_total + b->total_deposited - b->total_withdrawn;
    double diff     = fabs(total - expected);

    printf("\n  -- CONSISTENCY REPORT --\n");
    printf("  Initial:    Rs.%.2f\n",  b->initial_total);
    printf("  Deposited: +Rs.%.2f\n",  b->total_deposited);
    printf("  Withdrawn: -Rs.%.2f\n",  b->total_withdrawn);
    printf("  Expected:   Rs.%.2f\n",  expected);
    printf("  Actual:     Rs.%.2f\n",  total);
    printf("  Result:     %s\n", diff > 0.01 ? "[FAIL] Discrepancy detected!" : "[OK] Consistent");
}

static void *client_thread(void *arg)
{
    ThreadArg *ta = (ThreadArg *)arg;
    Bank *b   = ta->bank;
    int   tid = ta->thread_id;
    int   vip = ta->is_vip;
    int   n   = b->num_accounts;

    usleep(vip ? 500u : (unsigned)(tid * 4000));

    for (int i = 0; i < ta->num_ops; i++) {
        int    op     = rand() % 3;
        int    acc    = rand() % n;
        double amount = (double)((rand() % 5000) + 400);

        if (rand() % 12 == 0) amount = 8500.0 + (rand() % 1000);

        switch (op) {
            case 0: txn_deposit (b, acc, amount, tid, vip); break;
            case 1: txn_withdraw(b, acc, amount, tid, vip); break;
            case 2: {
                int dst = (acc + 1 + rand() % (n - 1)) % n;
                txn_transfer(b, acc, dst, amount / 2.0, tid, vip);
                break;
            }
        }
        usleep((unsigned)(rand() % 20000 + 5000));
    }
    return NULL;
}

static int admin_gate(void)
{
    printf("\n  Admin access required.\n");
    return check_admin_password();
}

static void run_simulation(Bank *b)
{
    if (!admin_gate()) { press_enter(); return; }

    clear_screen();
    print_banner();
    printf("  -- AUTO SIMULATION --\n");
    printf("  Threads: %d  (%d VIP + %d Normal)\n",
           SIM_CLIENTS, SIM_VIP, SIM_CLIENTS - SIM_VIP);
    printf("  Ops/thread: %d  |  Semaphore cap: %d\n\n",
           SIM_OPS, MAX_CONCURRENT_TXN);

    b->live_feed = 1;

    pthread_t threads[SIM_CLIENTS];
    ThreadArg args[SIM_CLIENTS];

    for (int i = 0; i < SIM_CLIENTS; i++) {
        args[i].bank      = b;
        args[i].thread_id = i + 1;
        args[i].is_vip    = (i < SIM_VIP) ? 1 : 0;
        args[i].num_ops   = SIM_OPS;
        pthread_create(&threads[i], NULL, client_thread, &args[i]);
    }

    for (int i = 0; i < SIM_CLIENTS; i++)
        pthread_join(threads[i], NULL);

    printf("\n  -- SIMULATION COMPLETE --\n");
    print_accounts(b);
    print_consistency(b);
    press_enter();
}

static int pick_account(Bank *b, const char *prompt)
{
    print_accounts(b);
    printf("\n  %s (1-%d, -1 to cancel): ", prompt, b->num_accounts);
    int id;
    if (scanf("%d", &id) != 1) { while (getchar() != '\n'); return -1; }
    while (getchar() != '\n');
    if (id < 1 || id > b->num_accounts) return -1;
    return id - 1;
}

static double pick_amount(void)
{
    printf("  Amount (Rs.): ");
    double amt;
    if (scanf("%lf", &amt) != 1) { while (getchar() != '\n'); return -1; }
    while (getchar() != '\n');
    return amt;
}

static void menu_deposit(Bank *b)
{
    clear_screen();
    printf("\n  -- DEPOSIT --\n");
    int id = pick_account(b, "Select account");
    if (id < 0) return;
    if (!check_pin(b, id)) return;

    double amt = pick_amount();
    if (amt <= 0) { printf("  Invalid amount.\n"); press_enter(); return; }

    b->live_feed = 0;
    int rc = txn_deposit(b, id, amt, 0, b->accounts[id].is_vip);
    b->live_feed = 1;

    if (rc == 0)
        printf("\n  [OK] Deposited Rs.%.2f into [%s]. New balance: Rs.%.2f\n",
               amt, b->accounts[id].owner, b->accounts[id].balance);
    else
        printf("\n  [FAIL] Deposit blocked.\n");
    press_enter();
}

static void menu_withdraw(Bank *b)
{
    clear_screen();
    printf("\n  -- WITHDRAW --\n");
    int id = pick_account(b, "Select account");
    if (id < 0) return;
    if (!check_pin(b, id)) return;

    double amt = pick_amount();
    if (amt <= 0) { printf("  Invalid amount.\n"); press_enter(); return; }

    b->live_feed = 0;
    int rc = txn_withdraw(b, id, amt, 0, b->accounts[id].is_vip);
    b->live_feed = 1;

    if (rc == 0)
        printf("\n  [OK] Withdrew Rs.%.2f from [%s]. New balance: Rs.%.2f\n",
               amt, b->accounts[id].owner, b->accounts[id].balance);
    else
        printf("\n  [FAIL] Withdrawal blocked.\n");
    press_enter();
}

static void menu_transfer(Bank *b)
{
    clear_screen();
    printf("\n  -- TRANSFER --\n");
    int src = pick_account(b, "Source account");
    if (src < 0) return;
    if (!check_pin(b, src)) return;

    int dst = pick_account(b, "Destination account");
    if (dst < 0 || dst == src) { printf("  Invalid destination.\n"); press_enter(); return; }

    double amt = pick_amount();
    if (amt <= 0) { printf("  Invalid amount.\n"); press_enter(); return; }

    b->live_feed = 0;
    int rc = txn_transfer(b, src, dst, amt, 0, b->accounts[src].is_vip);
    b->live_feed = 1;

    if (rc == 0)
        printf("\n  [OK] Transferred Rs.%.2f from [%s] to [%s].\n"
               "       Src: Rs.%.2f  |  Dst: Rs.%.2f\n",
               amt, b->accounts[src].owner, b->accounts[dst].owner,
               b->accounts[src].balance, b->accounts[dst].balance);
    else
        printf("\n  [FAIL] Transfer blocked.\n");
    press_enter();
}

static void menu_view_accounts(Bank *b)
{
    clear_screen();
    print_accounts(b);
    press_enter();
}

static void menu_view_log(Bank *b)
{
    if (!admin_gate()) { press_enter(); return; }
    clear_screen();
    printf("\n  -- TRANSACTION LOG --\n");
    if (b->log_count == 0) { printf("  No transactions yet.\n"); press_enter(); return; }
    printf("  Show last N (max %d): ", b->log_count);
    int n = 20;
    if (scanf("%d", &n) != 1) n = 20;
    while (getchar() != '\n');
    if (n <= 0 || n > b->log_count) n = b->log_count;
    print_log_tail(b, n);
    press_enter();
}

static void menu_freeze_unfreeze(Bank *b)
{
    if (!admin_gate()) { press_enter(); return; }
    clear_screen();
    printf("\n  -- FREEZE / UNFREEZE --\n");
    int id = pick_account(b, "Select account");
    if (id < 0) return;

    Account *a = &b->accounts[id];
    pthread_mutex_lock(&a->lock);
    a->frozen = !a->frozen;
    int f = a->frozen;
    pthread_mutex_unlock(&a->lock);

    printf("\n  [%s] Account [%s] is now %s.\n",
           f ? "FROZEN" : "ACTIVE", a->owner, f ? "frozen" : "active");
    press_enter();
}

static void menu_consistency(Bank *b)
{
    if (!admin_gate()) { press_enter(); return; }
    clear_screen();
    print_consistency(b);
    press_enter();
}

static void menu_os_concepts(void)
{
    clear_screen();
    printf("\n  -- OS CONCEPTS --\n\n");
    printf("  [1] Mutexes (pthread_mutex_t)\n"
           "      Per-account lock. Only one thread modifies a balance at a time.\n"
           "      Prevents race conditions.\n\n");
    printf("  [2] Semaphore (sem_t)\n"
           "      Limits concurrent transactions to %d (like teller windows).\n\n",
           MAX_CONCURRENT_TXN);
    printf("  [3] Deadlock Prevention\n"
           "      Transfers always lock the lower account index first.\n"
           "      Breaks circular-wait (Coffman condition).\n\n");
    printf("  [4] Race Condition Handling\n"
           "      Without mutex: two threads read same balance, both withdraw -> negative!\n"
           "      With mutex: second thread waits and sees updated balance.\n\n");
    printf("  [5] Fraud Detection\n"
           "      Transaction > Rs.%.0f freezes the account immediately.\n\n",
           FRAUD_THRESHOLD);
    printf("  [6] VIP Priority\n"
           "      VIP threads get a scheduling head-start via shorter usleep.\n\n");
    printf("  [7] Transaction Logger\n"
           "      All operations recorded atomically (protected by log_mutex).\n\n");
    printf("  [8] Consistency Verification\n"
           "      initial + deposited - withdrawn = final (verified after simulation).\n\n");
    press_enter();
}

static void main_menu(Bank *b)
{
    while (1) {
        clear_screen();
        print_banner();
        print_accounts(b);

        printf(
"\n  +----------------------------------------------------+\n"
"  |                   MAIN MENU                       |\n"
"  +----------------------------------------------------+\n"
"  |  [1] Deposit                    (PIN required)    |\n"
"  |  [2] Withdraw                   (PIN required)    |\n"
"  |  [3] Transfer                   (PIN required)    |\n"
"  |  [4] View accounts                                |\n"
"  |  [5] Transaction log            (ADMIN)           |\n"
"  |  [6] Freeze / Unfreeze          (ADMIN)           |\n"
"  |  [7] Consistency report         (ADMIN)           |\n"
"  |  [8] Run simulation             (ADMIN)           |\n"
"  |  [9] OS Concepts                                  |\n"
"  |  [0] Exit                                         |\n"
"  +----------------------------------------------------+\n");

        printf("  Choice: ");
        int ch;
        if (scanf("%d", &ch) != 1) { while (getchar() != '\n'); continue; }
        while (getchar() != '\n');

        switch (ch) {
            case 1: menu_deposit        (b); break;
            case 2: menu_withdraw       (b); break;
            case 3: menu_transfer       (b); break;
            case 4: menu_view_accounts  (b); break;
            case 5: menu_view_log       (b); break;
            case 6: menu_freeze_unfreeze(b); break;
            case 7: menu_consistency    (b); break;
            case 8: run_simulation      (b); break;
            case 9: menu_os_concepts    ();  break;
            case 0:
                clear_screen();
                print_banner();
                print_consistency(b);
                printf("\n  Goodbye!\n\n");
                return;
            default:
                printf("  Invalid option.\n");
                usleep(400000);
        }
    }
}

int main(void)
{
    srand((unsigned)time(NULL));

    Bank bank;
    bank_init(&bank);

    bank_add_account(&bank, 1, "Kamran Mirza",   "1111", 10000.0, 1);
    bank_add_account(&bank, 2, "Tariq Butt",     "2222",  8000.0, 1);
    bank_add_account(&bank, 3, "Sana Baig",      "3333",  5000.0, 0);
    bank_add_account(&bank, 4, "Bilal Chaudhry", "4444",  7500.0, 0);
    bank_add_account(&bank, 5, "Rabia Naqvi",    "5555",  6000.0, 0);
    bank_add_account(&bank, 6, "Imran Siddiqui", "6666",  4500.0, 0);
    bank_add_account(&bank, 7, "Faisal Sheikh",  "7777",  9000.0, 0);
    bank_add_account(&bank, 8, "Huma Rashid",    "8888",  3000.0, 0);

    main_menu(&bank);
    bank_destroy(&bank);
    return 0;
}
