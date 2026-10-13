/* MIT. Read-only bounded overlay reader. No game addresses, allocations or hooks. */
#ifndef CHS_OVERLAY_CORE_H
#define CHS_OVERLAY_CORE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define CHS_MAX_PACK (64u*1024u*1024u)
#define CHS_MAX_TEXT (1024u*1024u)
typedef struct { const uint8_t *data; size_t size; uint32_t count; } ChsPack;
typedef struct { const char *text; uint32_t length; } ChsText;
static uint32_t chs_u32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static int chs_span(const uint8_t *b,size_t n,uint32_t off,uint32_t len,size_t floor){
    return len>0 && len<=CHS_MAX_TEXT && off>=floor && off<n && len<n-off && b[off+len]==0 && !memchr(b+off,0,len);
}
static int ChsOpen(ChsPack *p,const void *data,size_t n,const uint8_t mapping[32]){
    const uint8_t *b=(const uint8_t*)data;uint32_t count,prev=0;size_t floor;
    if(!p)return 0;memset(p,0,sizeof(*p));
    if(!b || !mapping || n<48 || n>CHS_MAX_PACK || memcmp(b,"CHSOVL1\0",8) || chs_u32(b+8)!=1 || memcmp(b+16,mapping,32))return 0;
    count=chs_u32(b+12);if(count>(n-48)/20)return 0;floor=48+(size_t)count*20;
    for(uint32_t i=0;i<count;i++){
        const uint8_t *r=b+48+(size_t)i*20;uint32_t ref=chs_u32(r);
        if(ref>=0x1000000u || (i && ref<prev) || !chs_span(b,n,chs_u32(r+4),chs_u32(r+8),floor) || !chs_span(b,n,chs_u32(r+12),chs_u32(r+16),floor))return 0;
        prev=ref;
    }
    p->data=b;p->size=n;p->count=count;return 1;
}
/* 0: fall back; 1: matched; -1: conflicting translations, fall back. */
static int ChsResolve(const ChsPack *packs,size_t n,uint32_t fullref,const char *before,size_t len,ChsText *out){
    uint32_t ref=fullref&0xffffffu;int matched=0;
    if(!out)return 0;memset(out,0,sizeof(*out));
    if(fullref==0xffffffffu || !before || !len || !packs)return 0;
    for(size_t k=0;k<n;k++){
        const ChsPack *p=packs+k;uint32_t low=0,high=p->count;
        if(!p->data)continue;
        while(low<high){uint32_t mid=low+(high-low)/2;uint32_t value=chs_u32(p->data+48+(size_t)mid*20);if(value<ref)low=mid+1;else high=mid;}
        for(uint32_t i=low;i<p->count;i++){
            const uint8_t *r=p->data+48+(size_t)i*20;if(chs_u32(r)!=ref)break;
            uint32_t bo=chs_u32(r+4),bl=chs_u32(r+8),ao=chs_u32(r+12),al=chs_u32(r+16);
            if(bl!=len || memcmp(p->data+bo,before,len))continue;
            if(matched && (out->length!=al || memcmp(out->text,p->data+ao,al))){memset(out,0,sizeof(*out));return -1;}
            out->text=(const char*)(p->data+ao);out->length=al;matched=1;
        }
    }
    return matched;
}
#endif
