#ifndef __FEMU_BBSSD_FTL_TRACE_H
#define __FEMU_BBSSD_FTL_TRACE_H

#include <stdbool.h>
#include <stdint.h>

struct ssd;

/* Paper C trace mode (ftl-trace.c). All calls are no-ops unless FEMU_RFTL=trace. */
void ftl_trace_init(struct ssd *ssd);
void ftl_trace_free(struct ssd *ssd);
void ftl_trace_tick(struct ssd *ssd);
/* I/O path: copy the old bytes of the pages a write (or, with whole_only, a TRIM) is about to replace */
void ftl_trace_preimage(struct ssd *ssd, uint64_t off, uint64_t len, bool whole_only);
/* FTL: a host write of @lpn is committed; @was_mapped tells whether it replaces a mapped page */
void ftl_trace_write(struct ssd *ssd, uint64_t lpn, bool was_mapped);
/* FTL: a TRIM of the mapped @lpn, and of an @lpn that is not mapped */
void ftl_trace_trim(struct ssd *ssd, uint64_t lpn);
void ftl_trace_trim_unmapped(struct ssd *ssd, uint64_t lpn);
void ftl_trace_read(struct ssd *ssd, uint64_t lpn);

#endif
