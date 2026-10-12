/* Optional CHS-only cumulative font measurement, x86 Steam Aspyr build. */
#ifndef KOTOR_FONT_SCALE_FIX_H
#define KOTOR_FONT_SCALE_FIX_H
#include <stdint.h>
#include <math.h>
typedef struct {
    void* frame; void* font; const unsigned char* start; const unsigned char* next;
    double sum; float scale;
} FontScaleCache;
static DWORD fontScaleTls=TLS_OUT_OF_INDEXES;
static volatile LONG fontScaleApplied;
static double FontRawWidth(const unsigned char* font,unsigned char c) {
    const float* upper=*(const float* const*)(font+0x18);
    const float* lower=*(const float* const*)(font+0x24);
    return ((double)lower[c*3]-(double)upper[c*3])*(double)*(const float*)(font+0x0c)
         +(double)*(const float*)(font+0x10);
}
static int FontIsComposite(const unsigned char* font) {
    if(!font || IsBadReadPtr(font,0x28)) return 0;
    const void* upper=*(const void* const*)(font+0x18);
    const void* lower=*(const void* const*)(font+0x24);
    if(!upper || !lower || IsBadReadPtr(upper,3072) || IsBadReadPtr(lower,3072)) return 0;
    double reset=FontRawWidth(font,252),advance=FontRawWidth(font,249);
    return reset < -0.08 && advance > 0.08 && fabs(reset+advance)<0.00001
        && FontRawWidth(font,128)>0.003 && FontRawWidth(font,250)<-0.003;
}
/* The input is exactly the value already prepared for the native ftol call.
   ASCII/non-CHS fonts use its original truncation. Never hook global ftol. */
static int __attribute__((used,noinline)) FontScaleMeasure(void* frame,int mode,double originalInput) {
    unsigned char* f=(unsigned char*)frame;
    const unsigned char* font=*(const unsigned char**)(f-0x1c);
    if(!FontIsComposite(font) || fontScaleTls==TLS_OUT_OF_INDEXES) return (int)originalInput;
    const unsigned char* object=*(const unsigned char**)(f-0x60);
    const unsigned char* start=*(const unsigned char**)(f-0x14);
    const unsigned char* cursor=*(const unsigned char**)(f-0x0c);
    if(!object || !start || !cursor || cursor<start || (uintptr_t)cursor-(uintptr_t)start>0x400000 || IsBadReadPtr(object,0x58)) return (int)originalInput;
    float scale=*(const float*)(object+0x54);
    if(!isfinite(scale) || scale<=0 || scale>8) return (int)originalInput;
    FontScaleCache* cache=(FontScaleCache*)TlsGetValue(fontScaleTls);
    if(!cache) {
        cache=(FontScaleCache*)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof(*cache));
        if(!cache || !TlsSetValue(fontScaleTls,cache)) return (int)originalInput;
    }
    if(mode==0 || cache->frame!=frame || cache->font!=font || cache->start!=start || cache->scale!=scale || !cache->next || cursor<cache->next-1) {
        cache->frame=frame;cache->font=(void*)font;cache->start=start;cache->next=start;cache->sum=0;cache->scale=scale;
    }
    const unsigned char* end=cursor+1;
    /* Forward scan is amortized linear; a backward native restart recomputes
       the current line, not the entire string or previous lines. */
    if(cache->next>end || IsBadReadPtr(cache->next,(size_t)(end-cache->next))) return (int)originalInput;
    while(cache->next<end) cache->sum+=FontRawWidth(font,*cache->next++)*(double)scale*100.0;
    if(!isfinite(cache->sum) || cache->sum>2147480000.0 || cache->sum<-2147480000.0) return (int)originalInput;
    int measured=(int)(cache->sum+0.25);
    return mode==1 ? measured-*(int*)(f-0x2c) : measured;
}
#define FONT_SCALE_WRAPPER(name,mode) \
static void __attribute__((naked,used)) name(void) { \
    __asm__ volatile("pushl %ecx\n\tpushl %edx\n\tsubl $8,%esp\n\tfstpl (%esp)\n\tpushl $" #mode "\n\tpushl %ebp\n\tcall _FontScaleMeasure\n\taddl $16,%esp\n\tpopl %edx\n\tpopl %ecx\n\tret"); \
}
FONT_SCALE_WRAPPER(FontScaleInitial,0)
FONT_SCALE_WRAPPER(FontScaleAccumulate,1)
static int ApplyFontScaleFix(BYTE* image) {
    IMAGE_DOS_HEADER* dos=(IMAGE_DOS_HEADER*)image;
    if(!image || dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>4096) return -1;
    IMAGE_NT_HEADERS32* nt=(IMAGE_NT_HEADERS32*)(image+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386 ||
       nt->FileHeader.TimeDateStamp!=1443037277u || nt->OptionalHeader.SizeOfImage!=7049216u) return -2;
    static const DWORD offsets[]={0x7b020,0x7b238,0x7b4e2};
    void* targets[]={(void*)FontScaleInitial,(void*)FontScaleAccumulate,(void*)FontScaleInitial};
    BYTE original[3][5],replacement[3][5];DWORD protection[3],ignored;
    for(unsigned i=0;i<3;i++) {
        BYTE* p=image+offsets[i];memcpy(original[i],p,5);
        intptr_t source=(intptr_t)(image+0x51c860)-(intptr_t)(p+5);
        if(p[0]!=0xe8 || *(int32_t*)(p+1)!=(int32_t)source) return -3;
        replacement[i][0]=0xe8;intptr_t delta=(intptr_t)targets[i]-(intptr_t)(p+5);
        memcpy(replacement[i]+1,&delta,4);
    }
    fontScaleTls=TlsAlloc();if(fontScaleTls==TLS_OUT_OF_INDEXES) return -4;
    unsigned changed=0;
    for(;changed<3;changed++) {
        if(!VirtualProtect(image+offsets[changed],5,PAGE_EXECUTE_READWRITE,&protection[changed])) break;
    }
    if(changed!=3) {
        while(changed) { --changed;VirtualProtect(image+offsets[changed],5,protection[changed],&ignored); }
        TlsFree(fontScaleTls);fontScaleTls=TLS_OUT_OF_INDEXES;return -5;
    }
    for(unsigned i=0;i<3;i++) memcpy(image+offsets[i],replacement[i],5);
    FlushInstructionCache(GetCurrentProcess(),image,nt->OptionalHeader.SizeOfImage);
    /* These sites occupy the same executable page: restore its original
       protection once, in reverse order, after all three writes. */
    for(unsigned i=3;i;i--) VirtualProtect(image+offsets[i-1],5,protection[i-1],&ignored);
    InterlockedExchange(&fontScaleApplied,1);return 3;
}
static void InitializeFontScaleFix(void) {
    wchar_t path[MAX_PATH],ini[MAX_PATH],log[MAX_PATH];
    DWORD n=GetModuleFileNameW(NULL,path,MAX_PATH);if(!n || n>=MAX_PATH)return;
    wchar_t* slash=wcsrchr(path,L'\\');if(!slash || _wcsicmp(slash+1,L"swkotor2.exe"))return;slash[1]=0;
    if(wcslen(path)+32>=MAX_PATH)return;
    wcscpy(ini,path);wcscat(ini,L"swkotor2.ini");
    /* Enabled when absent; an explicit 0 remains an opt-out. */
    if(!GetPrivateProfileIntW(L"Chinese Text Fix",L"FontScaleFix",1,ini))return;
    int status=ApplyFontScaleFix((BYTE*)GetModuleHandleW(NULL));
    wcscpy(log,path);wcscat(log,L"FontScale-fix.log");
    HANDLE file=CreateFileW(log,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file!=INVALID_HANDLE_VALUE) {
        char text[160];DWORD written;int size=snprintf(text,sizeof(text),"FontScaleFix: status=%d; sites=3; CHS-only cumulative measurement; runtime verification pending\r\n",status);
        WriteFile(file,text,(DWORD)size,&written,NULL);CloseHandle(file);
    }
}
#endif
