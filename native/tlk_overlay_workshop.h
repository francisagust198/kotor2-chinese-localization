/* Data-only translation packs from Steam's active installed subscriptions.
 * No directory guessing, registration utility, extra DLL or INI opt-in.
 */
static void OverlayReport(uint32_t ref,const char *mode){static unsigned logs;if(logs++>=64)return;char text[160];snprintf(text,sizeof(text),"CHS: hit ref=%lu mode=%s",(unsigned long)ref,mode);Log(text);}
#define CHS_REPORT(ref,mode) OverlayReport(ref,mode)
#define CHS_OVERLAY_EMBEDDED
#ifndef CHS_DISCOVERY_TEST
#include "tlk_overlay_runtime.c"
#include "tlk_overlay_font_baseline.h"
#endif
static INIT_ONCE textOverlayOnce=INIT_ONCE_STATIC_INIT;
typedef struct {unsigned long long id;wchar_t folder[MAX_PATH];int hasManifest;} OverlayItem;
static int OverlayBasename(const wchar_t *name){
    if(!name[0]||wcschr(name,L'/')||wcschr(name,L'\\')||wcschr(name,L':')||wcsstr(name,L".."))return 0;
    for(const wchar_t *p=name;*p;p++)if(!(*p>=L'a'&&*p<=L'z')&&!(*p>=L'A'&&*p<=L'Z')&&!(*p>=L'0'&&*p<=L'9')&&*p!=L'.'&&*p!=L'_'&&*p!=L'-')return 0;
    return 1;
}
static int OverlayFonts(const wchar_t *game,OverlayItem *mods,unsigned n){
    wchar_t path[MAX_PATH];int provider=-1;
    for(unsigned i=0;i<n;i++)if(mods[i].id==3816191703ull)provider=(int)i;
    if(provider<0){Log("CHS: SKIP main localization not active/ready");return 0;}
    for(unsigned f=0;f<sizeof(overlayFontBaseline)/sizeof(overlayFontBaseline[0]);f++){
        _snwprintf(path,MAX_PATH,L"%ls\\override\\%ls",mods[provider].folder,overlayFontBaseline[f].name);
        if(!HashFile(path,overlayFontBaseline[f].hash)){Log("CHS: SKIP unsupported main font baseline");return 0;}
        _snwprintf(path,MAX_PATH,L"%lsoverride\\%ls",game,overlayFontBaseline[f].name);
        if(GetFileAttributesW(path)!=INVALID_FILE_ATTRIBUTES&&!HashFile(path,overlayFontBaseline[f].hash)&&(!overlayFontBaseline[f].rootHash[0]||!HashFile(path,overlayFontBaseline[f].rootHash))){Log("CHS: SKIP conflicting root font");return 0;}
        for(unsigned i=0;i<n;i++)if((int)i!=provider){
            _snwprintf(path,MAX_PATH,L"%ls\\override\\%ls",mods[i].folder,overlayFontBaseline[f].name);
            if(GetFileAttributesW(path)!=INVALID_FILE_ATTRIBUTES&&!HashFile(path,overlayFontBaseline[f].hash)){Log("CHS: SKIP conflicting active Workshop font");return 0;}
        }
    }
    return 1;
}
static int OverlayLoadManifest(const wchar_t *folder,unsigned long long id,size_t *total){
    wchar_t manifest[MAX_PATH],path[MAX_PATH],name[128],wideHash[80],section[32];
    _snwprintf(manifest,MAX_PATH,L"%ls\\localization\\chs-overlay.ini",folder);
    if(GetPrivateProfileIntW(L"Interface",L"Version",0,manifest)!=1 || GetPrivateProfileIntW(L"Interface",L"FontProvider",0,manifest)!=3816191703){Log("CHS: SKIP unsupported manifest version/provider");return 0;}
    unsigned n=GetPrivateProfileIntW(L"Interface",L"PackCount",0,manifest);
    if(!n||n>64){Log("CHS: SKIP invalid manifest pack count");return 0;}
    for(unsigned i=0;i<n;i++){
        _snwprintf(section,32,L"Pack%u",i);if(!GetPrivateProfileIntW(section,L"Enabled",1,manifest))continue;
        GetPrivateProfileStringW(section,L"File",L"",name,128,manifest);GetPrivateProfileStringW(section,L"SHA256",L"",wideHash,80,manifest);
        if(!OverlayBasename(name)||wcslen(wideHash)!=64){Log("CHS: SKIP invalid pack name/hash");return 0;}
        char hash[65];for(unsigned j=0;j<64;j++){if(!((wideHash[j]>=L'0'&&wideHash[j]<=L'9')||(wideHash[j]>=L'a'&&wideHash[j]<=L'f'))){Log("CHS: SKIP invalid checksum");return 0;}hash[j]=(char)wideHash[j];}hash[64]=0;
        _snwprintf(path,MAX_PATH,L"%ls\\localization\\%ls",folder,name);if(!HashFile(path,hash)){Log("CHS: SKIP translation checksum mismatch");return 0;}
        HANDLE h=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);if(h==INVALID_HANDLE_VALUE)return 0;
        LARGE_INTEGER len;DWORD got=0;uint8_t *data=NULL;
        if(GetFileSizeEx(h,&len)&&len.QuadPart>=48&&len.QuadPart<=CHS_MAX_PACK&&*total+(size_t)len.QuadPart<=CHS_MAX_PACK)data=HeapAlloc(GetProcessHeap(),0,(size_t)len.QuadPart);
        int ok=data&&ReadFile(h,data,(DWORD)len.QuadPart,&got,NULL)&&got==len.QuadPart&&ChsRegisterPack(data,got,overlayMapping);
        if(data)HeapFree(GetProcessHeap(),0,data);CloseHandle(h);
        if(!ok){Log("CHS: SKIP malformed pack or total budget exceeded");return 0;}
        *total+=got;char message[160];snprintf(message,sizeof(message),"CHS: registered workshop=%llu pack=%u bytes=%lu",id,i,(unsigned long)got);Log(message);
    }
    return 1;
}
static BOOL CALLBACK OverlayInit(PINIT_ONCE once,PVOID parameter,PVOID *context){
    (void)once;(void)parameter;(void)context;
    wchar_t game[MAX_PATH],ini[MAX_PATH],path[MAX_PATH];if(!GetDirectory(NULL,game))return TRUE;
    _snwprintf(logPath,MAX_PATH,L"%lsHighFPS-loader.log",game);_snwprintf(ini,MAX_PATH,L"%lsswkotor2.ini",game);
    if(!GetPrivateProfileIntW(L"Chinese Text Fix",L"TextOverlay",1,ini)){Log("CHS: disabled by explicit TextOverlay=0");return TRUE;}
    HMODULE steam=GetModuleHandleW(L"steam_api.dll");
    typedef int (__cdecl *GetUser)(void);typedef void* (__cdecl *GetUGC)(void);typedef unsigned (__cdecl *GetCount)(void*);typedef unsigned (__cdecl *GetItems)(void*,unsigned long long*,unsigned);
    typedef unsigned char (__cdecl *GetInstall)(void*,unsigned long long,unsigned long long*,char*,unsigned,unsigned char*);
    typedef unsigned char (__cdecl *GetUpdate)(void*,unsigned long long,unsigned char*,unsigned char*,unsigned long long*,unsigned long long*);
    GetUser user=steam?(GetUser)GetProcAddress(steam,"SteamAPI_GetHSteamUser"):NULL;GetUGC ugc=steam?(GetUGC)GetProcAddress(steam,"SteamUGC"):NULL;
    GetCount count=steam?(GetCount)GetProcAddress(steam,"SteamAPI_ISteamUGC_GetNumSubscribedItems"):NULL;GetItems items=steam?(GetItems)GetProcAddress(steam,"SteamAPI_ISteamUGC_GetSubscribedItems"):NULL;
    GetInstall install=steam?(GetInstall)GetProcAddress(steam,"SteamAPI_ISteamUGC_GetItemInstallInfo"):NULL;GetUpdate update=steam?(GetUpdate)GetProcAddress(steam,"SteamAPI_ISteamUGC_GetItemUpdateInfo"):NULL;
    if(!user||!ugc||!count||!items||!install||!update){Log("CHS: SKIP legacy Steam exports unavailable");return TRUE;}
    if(!user())return FALSE;
    void *service=ugc();if(!service)return TRUE;unsigned n=count(service);if(!n||n>4096){Log("CHS: no valid active subscription list");return TRUE;}
    unsigned long long *ids=HeapAlloc(GetProcessHeap(),0,n*sizeof(*ids));OverlayItem *mods=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,n*sizeof(*mods));
    if(!ids||!mods){if(ids)HeapFree(GetProcessHeap(),0,ids);if(mods)HeapFree(GetProcessHeap(),0,mods);return TRUE;}
    unsigned got=items(service,ids,n),ready=0,manifests=0;int incomplete=0;
    for(unsigned i=0;i<got&&i<n;i++){
        char folder[MAX_PATH]={0};unsigned char legacy=0,need=0,loading=0;unsigned long long size=0,done=0,total=0;
        if(!install(service,ids[i],&size,folder,MAX_PATH,&legacy)||legacy||!update(service,ids[i],&need,&loading,&done,&total)||need||loading){incomplete=1;break;}
        if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,folder,-1,mods[ready].folder,MAX_PATH)||wcslen(mods[ready].folder)>MAX_PATH-160){incomplete=1;break;}
        mods[ready].id=ids[i];_snwprintf(path,MAX_PATH,L"%ls\\localization\\chs-overlay.ini",mods[ready].folder);
        mods[ready].hasManifest=GetFileAttributesW(path)!=INVALID_FILE_ATTRIBUTES;manifests+=mods[ready].hasManifest;ready++;
    }
    if(incomplete)Log("CHS: SKIP active Workshop download unfinished; restart after completion");
    else if(manifests&&OverlayFonts(game,mods,ready)){
        size_t total=0;int ok=1;for(unsigned i=0;i<ready;i++)if(mods[i].hasManifest&&!OverlayLoadManifest(mods[i].folder,mods[i].id,&total)){ok=0;break;}
        if(ok&&total){if(ChsInstallFetchHook(overlayMapping))Log("CHS: ACTIVE Workshop text overlay; no installer or merged TLK");else Log("CHS: SKIP native hook preflight failed");}
    }else if(!manifests)Log("CHS: no active Workshop translation manifests");
    HeapFree(GetProcessHeap(),0,ids);HeapFree(GetProcessHeap(),0,mods);return TRUE;
}
static int InitializeTextOverlay(void){return InitOnceExecuteOnce(&textOverlayOnce,OverlayInit,NULL,NULL);}
