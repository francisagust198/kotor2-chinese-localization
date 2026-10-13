/* MIT. Explicitly installed research adapter for the hash-verified Steam EXE.
 * DllMain does not register packs or patch the game. Not a production release.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include "tlk_overlay_core.h"
typedef int (__attribute__((thiscall)) *FetchFn)(void*,uint32_t,void*,int);
typedef void* (__attribute__((thiscall)) *AssignFn)(void*,const char*);
typedef void (__attribute__((thiscall)) *ExpandFn)(void*,void*);
static FetchFn originalFetch;
static AssignFn assignString;
static ExpandFn expandTokens;
static ChsPack packs[64];static size_t packCount;static int installed;
static uint8_t activeMapping[32];static int haveMapping;
static unsigned hits,misses,conflicts;
#ifndef CHS_REPORT
#define CHS_REPORT(ref,mode) ((void)0)
#endif

__declspec(dllexport) int __cdecl ChsRegisterPack(const void *data,unsigned size,const uint8_t mapping[32]){
    ChsPack candidate;
    if(installed || packCount==64 || !ChsOpen(&candidate,data,size,mapping))return 0;
    if(haveMapping && memcmp(activeMapping,mapping,32))return 0;
    uint8_t *copy=HeapAlloc(GetProcessHeap(),0,size);if(!copy)return 0;
    memcpy(copy,data,size);
    if(!ChsOpen(&candidate,copy,size,mapping)){HeapFree(GetProcessHeap(),0,copy);return 0;}
    if(!haveMapping){memcpy(activeMapping,mapping,32);haveMapping=1;}
    packs[packCount++]=candidate;return 1;
}
static int __attribute__((fastcall,noinline)) OverlayFetch(void *self,void *unused,uint32_t ref,void *result,int parse){
    (void)unused;
    /* Experimental bound-local range; no high-byte namespace (native masks it).
     * Resource bindings must be checked for collisions by the package builder.
     */
    if(ref>=0xe00000u && ref<0xf00000u){
        ChsText bound;int chosen=ChsResolve(packs,packCount,ref,"@CHS-BOUND-LOCAL@",17,&bound);
        if(chosen==1){
            originalFetch(self,0xffffffffu,result,0);
            memset((uint8_t*)result+8,0,16);*(float*)((uint8_t*)result+24)=0.0f;
            assignString(result,bound.text);if(parse)expandTokens(self,result);hits++;CHS_REPORT(ref,"bound");return 1;
        }
        if(chosen<0)conflicts++;
        return originalFetch(self,ref,result,parse);
    }
    /* Ask for raw text. Comparing expanded text would break <CUSTOM*> guards. */
    int ok=originalFetch(self,ref,result,0);const char *raw=*(const char**)result;
    ChsText replacement;int selected=ok?ChsResolve(packs,packCount,ref,raw,raw?strlen(raw):0,&replacement):0;
    if(selected==1){
        assignString(result,replacement.text);if(parse)expandTokens(self,result);hits++;CHS_REPORT(ref,"overlay");return ok;
    }
    if(selected<0)conflicts++;else misses++;
    /* Preserve native behavior on a miss, including voice, fallback and notes. */
    return parse?originalFetch(self,ref,result,parse):ok;
}
__declspec(dllexport) void __cdecl ChsGetCounters(unsigned *h,unsigned *m,unsigned *c){if(h)*h=hits;if(m)*m=misses;if(c)*c=conflicts;}

#ifndef CHS_RUNTIME_TEST
static int SupportedFile(void){
    static const uint8_t expected[32]={0x6a,0x52,0x2e,0x71,0x63,0x1d,0xce,0xe9,0x34,0x67,0xbd,0x20,0x10,0xf3,0xb2,0x3d,0x91,0x45,0x32,0x6e,0x1e,0x2e,0x89,0x30,0x5f,0x13,0xab,0x10,0x4d,0xbb,0xff,0xef};
    wchar_t path[MAX_PATH];BCRYPT_ALG_HANDLE algorithm=NULL;BCRYPT_HASH_HANDLE hash=NULL;HANDLE file=INVALID_HANDLE_VALUE;int ok=0;uint8_t digest[32],buffer[65536];DWORD n;
    if(!GetModuleFileNameW(NULL,path,MAX_PATH))goto done;
    file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,0,NULL);if(file==INVALID_HANDLE_VALUE)goto done;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0 || BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0)<0)goto done;
    for(;;){if(!ReadFile(file,buffer,sizeof(buffer),&n,NULL))goto done;if(!n)break;if(BCryptHashData(hash,buffer,n,0)<0)goto done;}
    if(BCryptFinishHash(hash,digest,32,0)>=0)ok=!memcmp(expected,digest,32);
done:if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);return ok;
}
/* Invoke on the game thread BEFORE text caches are populated. Caller supplies
 * the verified active font-map identity; it must not trust a pack's identity.
 * No hot reload: restart after changing packs. Do not call from DllMain.
 */
__declspec(dllexport) int __cdecl ChsInstallFetchHook(const uint8_t verifiedMapping[32]){
    static const uint8_t signature[10]={0x55,0x8b,0xec,0x6a,0xff,0x68,0x26,0x01,0x96,0x00};
    static const uint8_t assignSignature[6]={0x55,0x8b,0xec,0x83,0xec,0x14};
    static const uint8_t expandSignature[3]={0x55,0x8b,0xec};
    uint8_t *site=(uint8_t*)0x71d970;DWORD old,ignored;
    if(installed || !haveMapping || !verifiedMapping || memcmp(activeMapping,verifiedMapping,32) || (uintptr_t)GetModuleHandleW(NULL)!=0x400000 || !SupportedFile())return 0;
    if(memcmp(site,signature,10) || memcmp((void*)0x7338d0,assignSignature,6) || memcmp((void*)0x71ebd0,expandSignature,3))return 0;
    uint8_t *trampoline=VirtualAlloc(NULL,10,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!trampoline)return 0;
    memcpy(trampoline,site,5);trampoline[5]=0xe9;int32_t back=(int32_t)((uintptr_t)(site+5)-(uintptr_t)(trampoline+10));memcpy(trampoline+6,&back,4);
    if(!VirtualProtect(trampoline,10,PAGE_EXECUTE_READ,&ignored)){VirtualFree(trampoline,0,MEM_RELEASE);return 0;}
    FlushInstructionCache(GetCurrentProcess(),trampoline,10);
    if(!VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&old)){VirtualFree(trampoline,0,MEM_RELEASE);return 0;}
    originalFetch=(FetchFn)trampoline;assignString=(AssignFn)0x7338d0;expandTokens=(ExpandFn)0x71ebd0;
    uint8_t jump[5]={0xe9};int32_t target=(int32_t)((uintptr_t)OverlayFetch-(uintptr_t)(site+5));memcpy(jump+1,&target,4);memcpy(site,jump,5);
    VirtualProtect(site,5,old,&ignored);FlushInstructionCache(GetCurrentProcess(),site,5);installed=1;return 1;
}
#ifndef CHS_OVERLAY_EMBEDDED
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,void *reserved){(void)reserved;if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
#endif
#endif
