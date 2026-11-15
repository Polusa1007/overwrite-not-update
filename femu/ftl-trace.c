/*
 * Trace mode for the FEMU black-box SSD (paper C).
 *
 * Records one 24-byte entry per host read, write and TRIM that the FTL
 * processes, and a mark when the run script sends "reset". The FTL's mapping,
 * garbage collection and timing are not changed: this file only observes.
 *
 * FEMU copies a write's payload into the DRAM backend before the FTL sees the
 * request, so the I/O path copies the old bytes of each page it is about to
 * overwrite (ftl_trace_preimage); the FTL takes them in arrival order per page.
 * The old contents of an overwrite count as known only if that copy has the
 * content hash of the page's last committed version.
 *
 * Environment (names kept from the build used for the campaigns, so that the
 * frozen run scripts work unchanged):
 *   FEMU_RFTL=trace          enable (any other value: off)
 *   FEMU_RFTL_TRACE=<path>   trace file (appended)
 *   FEMU_RFTL_CTL=<path>     control file (default /tmp/femu_rftl_ctl), polled
 *                            every 4096 requests or 50 ms of device time:
 *     "reset"        write a mark record, clear the counters, create <ctl>.done
 *     "dump <path>"  write the counters to <path>, then create <path>.done
 *
 * Record (little endian, packed): t_ns u64, lpn u32, ent u16 (0), diff u16,
 * clz u32, op u8, over u8, pad u16.
 *   op 1 write: over = 1 if it replaces a mapped page; if the old contents are
 *        known, diff = bytes that differ, clz = zlib level 1 size of the new
 *        page << 16, pad = zlib level 1 size of old XOR new (0xffff if 65535 or
 *        more); otherwise diff = 0xffff, clz = 0, pad = 0.
 *   op 2 TRIM of a mapped page, op 0 read, op 9 mark.
 */
#include "qemu/osdep.h"
#include "ftl.h"
#include "ftl-internal.h"
#include "ftl-trace.h"

#include <pthread.h>
#include <zlib.h>

struct trace_pre {
    struct trace_pre *next;
    uint8_t data[];
};

struct ftl_trace {
    char ctl[256];
    FILE *f;
    uint64_t *hash;                 /* content hash of each page's last committed version */
    pthread_mutex_t pre_lock;       /* the I/O path queues, the FTL thread takes */
    struct trace_pre **pre_head, **pre_tail;
    uint64_t nreq, last_poll;
    uint64_t host_writes, host_trims, base_nand, base_gc;
};

struct __attribute__((packed)) trace_rec {
    uint64_t t_ns;
    uint32_t lpn;
    uint16_t ent, diff;
    uint32_t clz;
    uint8_t op, over;
    uint16_t pad;
};

static uint64_t page_size_b(struct ssd *ssd)
{
    return (uint64_t)ssd->sp.secs_per_pg * ssd->sp.secsz;
}

static const uint8_t *page_bytes(struct ssd *ssd, uint64_t lpn)
{
    uint64_t pb = page_size_b(ssd), off = lpn * pb;

    if (!ssd->n || !ssd->n->mbe || !ssd->n->mbe->logical_space ||
        off + pb > (uint64_t)ssd->n->mbe->size) {
        return NULL;
    }
    return (const uint8_t *)ssd->n->mbe->logical_space + off;
}

static inline uint64_t mix64(uint64_t x)
{
    x += 0x9E3779B97F4A7C15ULL;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}

static uint64_t page_hash(const uint8_t *p, uint64_t pb)
{
    const uint64_t *w = (const uint64_t *)p;
    uint64_t h = 0x243F6A8885A308D3ULL;

    for (uint64_t i = 0; i < pb / 8; i++) {
        h = mix64(h ^ w[i]);
    }
    return h;
}

/* zlib level 1 size of p, or of p XOR x when x is given; 0xffff if it does not fit */
static uint16_t page_deflate(const uint8_t *p, const uint8_t *x, uint64_t pb)
{
    uLongf n = compressBound(pb);
    g_autofree uint8_t *out = g_malloc(n);
    g_autofree uint8_t *in = g_malloc(pb);

    for (uint64_t i = 0; i < pb; i++) {
        in[i] = x ? p[i] ^ x[i] : p[i];
    }
    if (compress2(out, &n, in, pb, 1) != Z_OK || n >= 0xffff) {
        return 0xffff;
    }
    return (uint16_t)n;
}

static void rec(struct ftl_trace *t, uint64_t now, uint64_t lpn, uint8_t op, bool over,
                uint16_t diff, uint32_t clz, uint16_t pad)
{
    struct trace_rec x = { now, (uint32_t)lpn, 0, diff, clz, op, over, pad };

    if (t->f) {
        fwrite(&x, sizeof(x), 1, t->f);
    }
}

void ftl_trace_init(struct ssd *ssd)
{
    const char *on = getenv("FEMU_RFTL"), *ctl = getenv("FEMU_RFTL_CTL"), *path = getenv("FEMU_RFTL_TRACE");
    struct ftl_trace *t;

    ssd->ftrace = NULL;
    if (!on || strcmp(on, "trace")) {
        return;
    }
    t = g_new0(struct ftl_trace, 1);
    snprintf(t->ctl, sizeof(t->ctl), "%s", ctl && *ctl ? ctl : "/tmp/femu_rftl_ctl");
    if (path && *path && (t->f = fopen(path, "ab"))) {
        setvbuf(t->f, NULL, _IOFBF, 1 << 20);
    }
    t->hash = g_new0(uint64_t, ssd->sp.tt_pgs);
    pthread_mutex_init(&t->pre_lock, NULL);
    t->pre_head = g_new0(struct trace_pre *, ssd->sp.tt_pgs);
    t->pre_tail = g_new0(struct trace_pre *, ssd->sp.tt_pgs);
    ssd->ftrace = t;
    fprintf(stderr, "[RFTL] trace only (ftl-trace.c): %d pages, ctl %s\n", ssd->sp.tt_pgs, t->ctl);
}

void ftl_trace_free(struct ssd *ssd)
{
    struct ftl_trace *t = ssd->ftrace;

    if (!t) {
        return;
    }
    for (int i = 0; i < ssd->sp.tt_pgs; i++) {
        while (t->pre_head[i]) {
            struct trace_pre *p = t->pre_head[i];
            t->pre_head[i] = p->next;
            g_free(p);
        }
    }
    if (t->f) {
        fclose(t->f);
    }
    g_free(t->pre_head); g_free(t->pre_tail); g_free(t->hash);
    pthread_mutex_destroy(&t->pre_lock);
    g_free(t);
    ssd->ftrace = NULL;
}

void ftl_trace_preimage(struct ssd *ssd, uint64_t off, uint64_t len, bool whole_only)
{
    struct ftl_trace *t = ssd ? ssd->ftrace : NULL;
    uint64_t pb, first, last;

    if (!t || !len) {
        return;
    }
    pb = page_size_b(ssd);
    first = off / pb;
    last = (off + len - 1) / pb;
    if (whole_only) {               /* a TRIM: only the pages it covers entirely */
        first = (off + pb - 1) / pb;
        if (off + len < pb) {
            return;
        }
        last = (off + len) / pb - 1;
    }
    for (uint64_t lpn = first; lpn <= last && first <= last; lpn++) {
        const uint8_t *src = lpn < (uint64_t)ssd->sp.tt_pgs ? page_bytes(ssd, lpn) : NULL;
        struct trace_pre *p;

        if (!src) {
            continue;
        }
        p = g_malloc(sizeof(*p) + pb);
        p->next = NULL;
        memcpy(p->data, src, pb);
        pthread_mutex_lock(&t->pre_lock);
        if (t->pre_tail[lpn]) {
            t->pre_tail[lpn]->next = p;
        } else {
            t->pre_head[lpn] = p;
        }
        t->pre_tail[lpn] = p;
        pthread_mutex_unlock(&t->pre_lock);
    }
}

/* the oldest queued old copy of @lpn (the FTL commits writes per page in arrival order), or NULL */
static struct trace_pre *take_pre(struct ftl_trace *t, uint64_t lpn)
{
    struct trace_pre *p;

    pthread_mutex_lock(&t->pre_lock);
    p = t->pre_head[lpn];
    if (p) {
        t->pre_head[lpn] = p->next;
        if (!p->next) {
            t->pre_tail[lpn] = NULL;
        }
    }
    pthread_mutex_unlock(&t->pre_lock);
    return p;
}

void ftl_trace_write(struct ssd *ssd, uint64_t lpn, bool was_mapped)
{
    struct ftl_trace *t = ssd->ftrace;
    const uint64_t pb = t ? page_size_b(ssd) : 0;
    const uint8_t *p;
    g_autofree struct trace_pre *pre = NULL;
    uint32_t d = 0xffff, clz = 0;
    uint16_t pad = 0;

    if (!t || lpn >= (uint64_t)ssd->sp.tt_pgs || !(p = page_bytes(ssd, lpn))) {
        return;
    }
    pre = take_pre(t, lpn);
    if (was_mapped && pre && page_hash(pre->data, pb) == t->hash[lpn]) {
        d = 0;
        for (uint64_t i = 0; i < pb; i++) {
            d += pre->data[i] != p[i];
        }
        pad = page_deflate(p, pre->data, pb);
        clz = (uint32_t)page_deflate(p, NULL, pb) << 16;
    }
    rec(t, ssd_now(ssd), lpn, 1, was_mapped, (uint16_t)d, clz, pad);
    t->host_writes++;
    t->hash[lpn] = page_hash(p, pb);
}

void ftl_trace_trim(struct ssd *ssd, uint64_t lpn)
{
    struct ftl_trace *t = ssd->ftrace;

    if (!t || lpn >= (uint64_t)ssd->sp.tt_pgs) {
        return;
    }
    rec(t, ssd_now(ssd), lpn, 2, true, 0, 0, 0);
    t->host_trims++;
    g_free(take_pre(t, lpn));       /* the DSM path queued the bytes it zeroed */
}

void ftl_trace_trim_unmapped(struct ssd *ssd, uint64_t lpn)
{
    struct ftl_trace *t = ssd->ftrace;

    if (t && lpn < (uint64_t)ssd->sp.tt_pgs) {
        g_free(take_pre(t, lpn));
    }
}

void ftl_trace_read(struct ssd *ssd, uint64_t lpn)
{
    struct ftl_trace *t = ssd->ftrace;

    if (t && lpn < (uint64_t)ssd->sp.tt_pgs) {
        rec(t, ssd_now(ssd), lpn, 0, false, 0, 0, 0);
    }
}

static void touch(const char *path)
{
    FILE *f = fopen(path, "w");

    if (f) {
        fclose(f);
    }
}

static void control(struct ssd *ssd)
{
    struct ftl_trace *t = ssd->ftrace;
    char line[300] = "", arg[260] = "", done[300];
    FILE *f = fopen(t->ctl, "r");

    if (!f) {
        return;
    }
    if (!fgets(line, sizeof(line), f)) {
        line[0] = '\0';
    }
    fclose(f);
    unlink(t->ctl);
    if (!strncmp(line, "reset", 5)) {
        t->host_writes = t->host_trims = 0;
        t->base_nand = ssd->nand_write_pages;
        t->base_gc = ssd->gc_write_pages;
        snprintf(done, sizeof(done), "%s.done", t->ctl);
        touch(done);
        rec(t, ssd_now(ssd), 0, 9, false, 0, 0, 0);
        if (t->f) {
            fflush(t->f);
        }
        fprintf(stderr, "[RFTL] counters reset\n");
    } else if (sscanf(line, "dump %255s", arg) == 1) {
        if ((f = fopen(arg, "w"))) {
            fprintf(f, "# host_writes=%" PRIu64 " host_trims=%" PRIu64 "\n", t->host_writes, t->host_trims);
            fprintf(f, "# retained_now=0 peak_retained=0\n");
            fprintf(f, "# nand_writes=%" PRIu64 " gc_writes=%" PRIu64 " tt_pgs=%d\n",
                    ssd->nand_write_pages - t->base_nand, ssd->gc_write_pages - t->base_gc, ssd->sp.tt_pgs);
            fclose(f);
            snprintf(done, sizeof(done), "%s.done", arg);
            touch(done);
        }
        if (t->f) {
            fflush(t->f);
        }
        fprintf(stderr, "[RFTL] dumped to %s\n", arg);
    }
}

void ftl_trace_tick(struct ssd *ssd)
{
    struct ftl_trace *t = ssd->ftrace;
    uint64_t now;

    if (!t) {
        return;
    }
    now = ssd_now(ssd);
    if ((++t->nreq & 4095) == 0 || now - t->last_poll > 50000000ULL) {
        t->last_poll = now;
        control(ssd);
    }
}
