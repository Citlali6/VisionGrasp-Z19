/* SPDX-License-Identifier: Apache-2.0
 * Linux UIO map0, device memory must be mapped by the UIO kernel driver as
 * non-cacheable Device memory. Ordinary cached RAM is not an MMIO backend. */
#define _POSIX_C_SOURCE 200809L
#include "pspl.h"
#include "registers.h"
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#define VIDEO_ID UINT32_C(0x56475632)
#define AUDIO_ID UINT32_C(0x56474132)
#define GUARD_ID UINT32_C(0x31444753)
enum { ID=PSPL_R_ID, VERSION=PSPL_R_VERSION, CONTROL=PSPL_R_CONTROL,
       STATUS=PSPL_R_STATUS, ERROR=PSPL_R_ERROR, IN_COUNT=PSPL_R_IN_COUNT,
       OUT_COUNT=PSPL_R_OUT_COUNT, INPUT=PSPL_R_INPUT, OUTPUT=PSPL_R_OUTPUT,
       CFG=PSPL_R_CONFIG_VERSION, COMPLETE=PSPL_R_COMPLETE };
struct pspl_device {
    int fd, failed; volatile uint32_t *mmio; size_t size;
    uint32_t id, timeout_ms; pthread_mutex_t mutex;
};
static void barrier(void) {
#if defined(__aarch64__)
    __asm__ __volatile__("dmb osh" ::: "memory");
#else
    __sync_synchronize();
#endif
}
static uint32_t rd(pspl_device *d, uint32_t offset) {
    barrier(); uint32_t v=d->mmio[offset/4]; barrier(); return v;
}
static void wr(pspl_device *d, uint32_t offset, uint32_t v) {
    barrier(); d->mmio[offset/4]=v;
#if defined(__aarch64__)
    /* Complete the Device-memory store before reporting write success. */
    __asm__ __volatile__("dsb osh" ::: "memory");
#else
    barrier();
#endif
}
static int address_ok(pspl_device *d, uint32_t o) {
    return d && !(o&3) && d->size>=4 && o<=d->size-4;
}
static int now_ns(uint64_t *n) {
    struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) return -errno;
    *n=(uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec; return 0;
}
static int deadline(pspl_device *d,uint64_t *end) {
    int e=now_ns(end); if(e) return e;
    *end+=(uint64_t)d->timeout_ms*UINT64_C(1000000); return 0;
}
static int timed_out(uint64_t end) {
    uint64_t n; int e=now_ns(&n); return e ? e : n>=end ? -ETIMEDOUT : 0;
}
int pspl_open(const char *path,uint32_t id,size_t size,uint32_t timeout,
              pspl_device **out) {
    unsigned number; char tail, sysfs[128]; unsigned long long actual;
    if(!out) return -EINVAL;
    *out=NULL;
    if(!path || sscanf(path,"/dev/uio%u%c",&number,&tail)!=1 || !timeout ||
       size<4096 || (size&3) || (id!=VIDEO_ID && id!=AUDIO_ID && id!=GUARD_ID)) return -EINVAL;
    snprintf(sysfs,sizeof sysfs,"/sys/class/uio/uio%u/maps/map0/size",number);
    FILE *f=fopen(sysfs,"r"); if(!f) return -errno;
    int parsed=fscanf(f,"%llx",&actual); fclose(f);
    if(parsed!=1 || actual<size) return -ERANGE;
    pspl_device *d=calloc(1,sizeof *d); if(!d) return -ENOMEM;
    d->fd=open(path,O_RDWR|O_CLOEXEC|O_SYNC);
    if(d->fd<0) {int e=-errno; free(d); return e;}
    if(flock(d->fd,LOCK_EX|LOCK_NB)) {int e=-errno; close(d->fd); free(d); return e;}
    void *p=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,d->fd,0);
    if(p==MAP_FAILED) {int e=-errno; close(d->fd); free(d); return e;}
    d->mmio=p; d->size=size; d->id=id; d->timeout_ms=timeout;
    int e=pthread_mutex_init(&d->mutex,NULL);
    if(e) {munmap(p,size); close(d->fd); free(d); return -e;}
    uint32_t protocol=id==GUARD_ID?UINT32_C(0x00010000):1;
    if(rd(d,ID)!=id || rd(d,VERSION)!=protocol) {pspl_close(d); return -EPROTO;}
    *out=d; return 0;
}
void pspl_close(pspl_device *d) {
    if(!d) return;
    /* Caller must stop workers before close; no concurrent destruction. */
    munmap((void *)d->mmio,d->size); close(d->fd);
    pthread_mutex_destroy(&d->mutex); free(d);
}
int pspl_read(pspl_device *d,uint32_t o,uint32_t *v) {
    if(!v || !address_ok(d,o)) return -EINVAL;
    pthread_mutex_lock(&d->mutex); *v=rd(d,o); pthread_mutex_unlock(&d->mutex); return 0;
}
int pspl_write(pspl_device *d,uint32_t o,uint32_t v) {
    if(!address_ok(d,o)) return -EINVAL;
    pthread_mutex_lock(&d->mutex); wr(d,o,v);
    /* Register faults are observable without pretending Linux UIO exposes
     * AXI BRESP directly. Kernel bus aborts remain process-fatal failures. */
    int e=d->id==GUARD_ID ? ((rd(d,STATUS)&64)?-EIO:0) : (rd(d,ERROR)?-EIO:0);
    pthread_mutex_unlock(&d->mutex); return e;
}
int pspl_reset(pspl_device *d) {
    if(!d) return -EINVAL;
    if(d->id==GUARD_ID) return -ENOTSUP;
    pthread_mutex_lock(&d->mutex); wr(d,CONTROL,4);
    /* Device soft reset is synchronous; status read orders the preceding write. */
    (void)rd(d,STATUS); d->failed=0; pthread_mutex_unlock(&d->mutex); return 0;
}
static int pump(pspl_device *d,const void *in,void *out,size_t n,int video,
                uint32_t width,uint32_t *before) {
    uint64_t end; int e=deadline(d,&end); if(e) return e;
    size_t sent=0,received=0;
    uint32_t ic=rd(d,IN_COUNT), oc=rd(d,OUT_COUNT);
    *before=rd(d,COMPLETE);
    if(d->failed) return -EPIPE;
    if(rd(d,ERROR) || (rd(d,STATUS)&2)) return -EIO;
    while(received<n) {
        if(rd(d,ERROR)) return -EIO;
        uint32_t s=rd(d,STATUS);
        if(s&2) {
            uint32_t v=rd(d,OUTPUT);
            if(received>=sent) return -EPROTO;
            if(video) {
                uint32_t tags=((received==0)?1u<<24:0u)|
                    ((received%width==width-1)?1u<<25:0u);
                if((v&UINT32_C(0x03000000))!=tags || (v&UINT32_C(0xf8000000)))
                    return -EPROTO;
                ((uint32_t*)out)[received]=v;
            } else ((int16_t*)out)[received]=(int16_t)(v&0xffff);
            ++received;
        }
        if(sent<n && (s&1)) {
            uint32_t v=video?((const uint32_t*)in)[sent]:
                (uint16_t)((const int16_t*)in)[sent];
            wr(d,INPUT,v); ++sent;
        }
        e=timed_out(end); if(e) return e;
    }
    if(sent!=n || (uint32_t)(rd(d,IN_COUNT)-ic)!=(uint32_t)n ||
       (uint32_t)(rd(d,OUT_COUNT)-oc)!=(uint32_t)n || rd(d,ERROR)) return -EPROTO;
    return 0;
}
int pspl_audio_process(pspl_device *d,const int16_t *in,int16_t *out,size_t n) {
    if(!d || d->id!=AUDIO_ID || !in || !out || !n || n>UINT32_MAX) return -EINVAL;
    pthread_mutex_lock(&d->mutex); uint32_t before;
    int e=(rd(d,STATUS)&4)?-EPIPE:pump(d,in,out,n,0,0,&before);
    if(!e && ((uint32_t)(rd(d,COMPLETE)-before)!=(uint32_t)n || (rd(d,STATUS)&4))) e=-EPROTO;
    if(e) d->failed=1;
    pthread_mutex_unlock(&d->mutex); return e;
}
int pspl_video_process(pspl_device *d,const uint32_t *in,uint32_t *out,
                       size_t n,uint32_t w,uint32_t h,pspl_video_stats *s) {
    if(!d || d->id!=VIDEO_ID || !in || !out || !s || !w || !h ||
       w>4096 || h>4096 || n!=(size_t)w*h) return -EINVAL;
    for(size_t i=0;i<n;++i) {
        uint32_t tags=(i==0?1u<<24:0u)|(i%w==w-1?1u<<25:0u);
        if((in[i]&UINT32_C(0xff000000))!=tags) return -EINVAL;
    }
    pthread_mutex_lock(&d->mutex); uint32_t before;
    int e=pump(d,in,out,n,1,w,&before); uint64_t end=0;
    if(!e) e=deadline(d,&end);
    while(!e && !(rd(d,STATUS)&16)) e=timed_out(end);
    if(!e) {
        uint32_t frame=rd(d,PSPL_V_FRAME);
        s->frame_id=frame; s->count=rd(d,PSPL_V_COUNT);
        s->xmin=rd(d,PSPL_V_XMIN); s->ymin=rd(d,PSPL_V_YMIN);
        s->xmax=rd(d,PSPL_V_XMAX); s->ymax=rd(d,PSPL_V_YMAX);
        s->sum_x=rd(d,PSPL_V_SUM_X_LO)|((uint64_t)rd(d,PSPL_V_SUM_X_HI)<<32);
        s->sum_y=rd(d,PSPL_V_SUM_Y_LO)|((uint64_t)rd(d,PSPL_V_SUM_Y_HI)<<32);
        s->valid=rd(d,PSPL_V_VALID); s->config_version=rd(d,CFG);
        if(rd(d,PSPL_V_FRAME)!=frame || frame!=before+1 || rd(d,COMPLETE)!=frame ||
           !(s->valid&1) || rd(d,ERROR)) e=-EPROTO;
        if(!e) wr(d,CONTROL,(rd(d,CONTROL)&3)|16);
    }
    if(e) d->failed=1;
    pthread_mutex_unlock(&d->mutex); return e;
}
