// KOTOR II Workshop High FPS bootstrap, x86 Windows.
// Only the allowlisted Workshop item may provide native payloads.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "highfps_hooks.h"
#ifndef WORKSHOP_ID
#define WORKSHOP_ID L"0"
#endif

static HMODULE selfModule, realInput, runtimeModule;
static int InitializeTextOverlay(void);
static INIT_ONCE realOnce = INIT_ONCE_STATIC_INIT;
static INIT_ONCE patchOnce = INIT_ONCE_STATIC_INIT;
static wchar_t logPath[MAX_PATH];
static volatile LONG* callbackSlot;
static void (__cdecl *originalCallbacks)(void);

static void Log(const char* message) {
    OutputDebugStringA(message);
    if (!logPath[0]) return;
    HANDLE f = CreateFileW(logPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                          NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        DWORD written;
        WriteFile(f, message, (DWORD)strlen(message), &written, NULL);
        WriteFile(f, "\r\n", 2, &written, NULL);
        CloseHandle(f);
    }
}

#ifdef HFP_CURSOR_TRACE
static int GetDirectory(HMODULE module, wchar_t* path);
static int (WINAPI *originalShowCursor)(BOOL);
static HCURSOR (WINAPI *originalSetCursor)(HCURSOR);
static BOOL (WINAPI *originalScreenToClient)(HWND,LPPOINT);
static BOOL WINAPI TraceScreenToClient(HWND window, LPPOINT point) {
    POINT before=*point;
    BOOL ok=originalScreenToClient(window,point);
    static POINT last={-32768,-32768};
    static unsigned count;
    DWORD pid=0;
    GetWindowThreadProcessId(window,&pid);
    if (ok && pid==GetCurrentProcessId() && count<128 &&
        (before.x!=last.x || before.y!=last.y)) {
        last=before; ++count;
        RECT bounds,client;
        POINT origin={0,0},physical;
        GetWindowRect(window,&bounds); GetClientRect(window,&client);
        ClientToScreen(window,&origin); GetCursorPos(&physical);
        char line[320];
        snprintf(line,sizeof(line),"COORD: caller=%p screen=%ld,%ld client=%ld,%ld actual=%ld,%ld origin=%ld,%ld rect=%ld,%ld,%ld,%ld size=%ld,%ld",
                 __builtin_return_address(0),before.x,before.y,point->x,point->y,physical.x,physical.y,
                 origin.x,origin.y,bounds.left,bounds.top,bounds.right,bounds.bottom,client.right,client.bottom);
        Log(line);
    }
    return ok;
}
static INIT_ONCE cursorTraceOnce = INIT_ONCE_STATIC_INIT;
static unsigned cursorTraceCount;
static void TraceCursor(const char* event, void* caller, int value, HCURSOR cursor) {
    if (++cursorTraceCount > 512) return;
    CURSORINFO info = { sizeof(info) };
    GetCursorInfo(&info);
    char line[256];
    snprintf(line, sizeof(line), "CURSOR: %s caller=%p value=%d handle=%p flags=%lu current=%p thread=%lu",
             event, caller, value, cursor, info.flags, info.hCursor, GetCurrentThreadId());
    Log(line);
}
static int WINAPI TraceShowCursor(BOOL show) {
    int count = originalShowCursor(show);
    TraceCursor(show ? "ShowCursor(TRUE)" : "ShowCursor(FALSE)", __builtin_return_address(0), count, NULL);
    return count;
}
static HCURSOR WINAPI TraceSetCursor(HCURSOR cursor) {
    static HCURSOR previous = (HCURSOR)-1;
    HCURSOR displayed = cursor;
#ifdef HFP_CURSOR_SYSTEM_ARROW
    if (cursor) displayed = LoadCursorW(NULL, MAKEINTRESOURCEW(32512));
#endif
    HCURSOR old = originalSetCursor(displayed);
    if (cursor != previous) {
        TraceCursor("SetCursor", __builtin_return_address(0), 0, cursor);
        previous = cursor;
    }
    return old;
}
// Diagnostics only: observe the game's existing cursor calls, preserving their
// arguments, return values and calling convention. Not part of published DLL.
static BOOL CALLBACK InstallCursorTrace(PINIT_ONCE once, PVOID parameter, PVOID* context) {
    (void)once; (void)parameter; (void)context;
    wchar_t game[MAX_PATH];
    if (!GetDirectory(NULL, game)) return TRUE;
    _snwprintf(logPath, MAX_PATH, L"%lsHighFPS-loader.log", game);
    unsigned char* image = (unsigned char*)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER* dos = (void*)image;
    IMAGE_NT_HEADERS32* nt = (void*)(image + dos->e_lfanew);
    IMAGE_IMPORT_DESCRIPTOR* imports = (void*)(image + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    for (; imports->Name; ++imports) {
        if (_stricmp((char*)image + imports->Name, "USER32.dll")) continue;
        IMAGE_THUNK_DATA32* names = (void*)(image + imports->OriginalFirstThunk);
        IMAGE_THUNK_DATA32* slots = (void*)(image + imports->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            IMAGE_IMPORT_BY_NAME* name = (void*)(image + names->u1.AddressOfData);
            FARPROC hook = NULL;
            if (!strcmp((char*)name->Name, "ShowCursor")) {
                originalShowCursor = (void*)slots->u1.Function; hook = (FARPROC)TraceShowCursor;
            } else if (!strcmp((char*)name->Name, "SetCursor")) {
                originalSetCursor = (void*)slots->u1.Function; hook = (FARPROC)TraceSetCursor;
            } else if (!strcmp((char*)name->Name, "ScreenToClient")) {
                originalScreenToClient = (void*)slots->u1.Function; hook = (FARPROC)TraceScreenToClient;
            }
            if (hook) {
                DWORD old, ignored;
                if (VirtualProtect(&slots->u1.Function, sizeof(DWORD), PAGE_READWRITE, &old)) {
                    InterlockedExchange((volatile LONG*)&slots->u1.Function, (LONG)hook);
                    VirtualProtect(&slots->u1.Function, sizeof(DWORD), old, &ignored);
                }
            }
        }
    }
#ifdef HFP_CURSOR_SYSTEM_ARROW
    Log("CURSOR: diagnostic standard arrow replacement enabled");
#else
    Log("CURSOR: trace installed; no visibility overrides");
#endif
    return TRUE;
}
#endif

static int GetDirectory(HMODULE module, wchar_t* path) {
    DWORD n = GetModuleFileNameW(module, path, MAX_PATH);
    if (!n || n >= MAX_PATH) return 0;
    wchar_t* slash = wcsrchr(path, L'\\');
    if (!slash) return 0;
    slash[1] = 0;
    return 1;
}

typedef struct { HWND window; long area; } BorderlessTarget;
static HWND borderlessWindow;
static WNDPROC originalWindowProc;
static LRESULT CALLBACK BorderlessWindowProc(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == WM_ACTIVATEAPP || message == WM_ACTIVATE) {
        BOOL active = message == WM_ACTIVATEAPP ? (BOOL)wParam : LOWORD(wParam) != WA_INACTIVE;
        SetWindowPos(window, active ? HWND_TOPMOST : HWND_NOTOPMOST, 0,0,0,0,
                     SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);
    }
    return CallWindowProcA(originalWindowProc,window,message,wParam,lParam);
}
static BOOL CALLBACK FindGameWindow(HWND window, LPARAM parameter) {
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid != GetCurrentProcessId() || GetWindow(window, GW_OWNER)) return TRUE;
    RECT client;
    if (!GetClientRect(window, &client)) return TRUE;
    long area = (client.right-client.left)*(client.bottom-client.top);
    BorderlessTarget* target = (void*)parameter;
    if (area > target->area) { target->area=area; target->window=window; }
    return TRUE;
}
static void ApplyBorderless(void) {
    wchar_t game[MAX_PATH], ini[MAX_PATH];
    if (!GetDirectory(NULL, game)) return;
    _snwprintf(ini, MAX_PATH, L"%lsswkotor2.ini", game);
    if (!GetPrivateProfileIntW(L"Graphics Options",L"BorderlessWindow",0,ini)) return;
    if (GetPrivateProfileIntW(L"Graphics Options",L"FullScreen",1,ini)) {
        Log("DISPLAY: borderless requires windowed game configuration"); return;
    }
    BorderlessTarget target = {NULL, 40000};
    EnumWindows(FindGameWindow,(LPARAM)&target);
    if (!target.window) { Log("DISPLAY: game window unavailable for borderless"); return; }
    MONITORINFO monitor = {sizeof(monitor)};
    if (!GetMonitorInfoW(MonitorFromWindow(target.window,MONITOR_DEFAULTTONEAREST),&monitor)) return;
    LONG style = GetWindowLongW(target.window,GWL_STYLE);
    SetWindowLongW(target.window,GWL_STYLE,(style & ~WS_OVERLAPPEDWINDOW)|WS_POPUP);
    if (!borderlessWindow) {
        SetLastError(0);
        LONG oldProc = SetWindowLongA(target.window,GWL_WNDPROC,(LONG)BorderlessWindowProc);
        if (!oldProc && GetLastError()) { Log("DISPLAY: cannot install focus handling"); return; }
        originalWindowProc = (WNDPROC)oldProc;
        borderlessWindow = target.window;
    }
    RECT r = monitor.rcMonitor;
    int inset = GetPrivateProfileIntW(L"Graphics Options",L"BorderlessInset",0,ini);
    if (inset >= 1 && inset <= 8) r.bottom -= inset;
    if (!SetWindowPos(target.window,GetForegroundWindow()==target.window ? HWND_TOPMOST : HWND_NOTOPMOST,
                      r.left,r.top,r.right-r.left,r.bottom-r.top,SWP_FRAMECHANGED|SWP_NOACTIVATE)) {
        Log("DISPLAY: failed to size borderless window"); return;
    }
    char line[160];
    snprintf(line,sizeof(line),"DISPLAY: borderless window %ldx%ld; hardware cursor uses windowed rendering",r.right-r.left,r.bottom-r.top);
    Log(line);
}

static int HashFile(const wchar_t* path, const char* expected) {
    BCRYPT_ALG_HANDLE alg = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    HANDLE f = INVALID_HANDLE_VALUE;
    DWORD got = 0;
    unsigned char digest[32], buffer[16384];
    int ok = 0;
    if (strlen(expected) != 64) return 0;
    if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, 0) < 0) goto done;
    if (BCryptCreateHash(alg, &hash, NULL, 0, NULL, 0, 0) < 0) goto done;
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) goto done;
    for (;;) {
        if (!ReadFile(f, buffer, sizeof(buffer), &got, NULL)) goto done;
        if (!got) break;
        if (BCryptHashData(hash, buffer, got, 0) < 0) goto done;
    }
    if (BCryptFinishHash(hash, digest, sizeof(digest), 0) < 0) goto done;
    for (int i = 0; i < 32; ++i) {
        unsigned value;
        if (sscanf(expected + 2*i, "%2x", &value) != 1 || digest[i] != value) goto done;
    }
    ok = 1;
done:
    if (f != INVALID_HANDLE_VALUE) CloseHandle(f);
    if (hash) BCryptDestroyHash(hash);
    if (alg) BCryptCloseAlgorithmProvider(alg, 0);
    return ok;
}

static int VerifyPayload(const wchar_t* directory) {
    const char* names[] = {"KotorPatcher.dll", "HighFpsFixes.dll", "patch_config.toml"};
    wchar_t path[MAX_PATH];
    _snwprintf(path, MAX_PATH, L"%lspayload.sha256", directory);
    FILE* f = _wfopen(path, L"rb");
    if (!f) return 0;
    char digest[65], name[64];
    int ok = 1;
    for (unsigned i = 0; i < 3; ++i) {
        if (fscanf(f, "%64s %63s", digest, name) != 2 || strcmp(name, names[i])) { ok = 0; break; }
        wchar_t wideName[64];
        if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, wideName, 64)) { ok = 0; break; }
        _snwprintf(path, MAX_PATH, L"%ls%ls", directory, wideName);
        if (!HashFile(path, digest)) { ok = 0; break; }
    }
    fclose(f);
    return ok;
}

static int Preflight(void) {
    for (unsigned i = 0; i < HFP_HOOK_COUNT; ++i) {
        const HfpHook* h = &hfpHooks[i];
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery((void*)h->address, &info, sizeof(info)) || info.State != MEM_COMMIT ||
            memcmp((void*)h->address, h->original, h->length)) return 0;
    }
    return 1;
}

static int VerifyApplied(void) {
    for (unsigned i = 0; i < HFP_HOOK_COUNT; ++i) {
        const HfpHook* h = &hfpHooks[i];
        if (h->simple) {
            if (memcmp((void*)h->address, h->replacement, h->length)) return 0;
        } else {
            unsigned char* site = (unsigned char*)h->address;
            if (site[0] != 0xE9) return 0;
            DWORD target = h->address + 5 + *(LONG*)(site + 1);
            MEMORY_BASIC_INFORMATION info;
            if (!VirtualQuery((void*)target, &info, sizeof(info)) || info.State != MEM_COMMIT ||
                !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE))) return 0;
        }
    }
    return 1;
}

static int Rollback(void) {
    int ok = 1;
    for (unsigned i = 0; i < HFP_HOOK_COUNT; ++i) {
        const HfpHook* h = &hfpHooks[i];
        DWORD old, ignored;
        if (!VirtualProtect((void*)h->address, h->length, PAGE_EXECUTE_READWRITE, &old)) { ok = 0; continue; }
        memcpy((void*)h->address, h->original, h->length);
        FlushInstructionCache(GetCurrentProcess(), (void*)h->address, h->length);
        VirtualProtect((void*)h->address, h->length, old, &ignored);
    }
    return ok;
}

static int LoadPayload(const wchar_t* directory) {
    if (!VerifyPayload(directory)) { Log("SKIP: payload missing or checksum mismatch"); return 0; }
    if (!Preflight()) { Log("SKIP: original hook bytes differ; conflicting native patch"); return 0; }
    wchar_t runtime[MAX_PATH];
    _snwprintf(runtime, MAX_PATH, L"%lsKotorPatcher.dll", directory);
    runtimeModule = LoadLibraryExW(runtime, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!runtimeModule) { Log("SKIP: native runtime failed to load"); return 0; }
    if (!VerifyApplied()) {
        Log(Rollback() ? "FAILED: incomplete patch; original code restored" : "FAILED: rollback could not restore all code");
        // Keep DLLs loaded: upstream generated wrappers remain owned until process exit.
        return 0;
    }
    Log("ACTIVE: High FPS Fixes 1.0.1; 29/29 hooks verified; EXE file unchanged");
    return 1;
}

static BOOL CALLBACK PatchInit(PINIT_ONCE once, PVOID parameter, PVOID* context) {
    (void)once; (void)parameter; (void)context;
    wchar_t game[MAX_PATH], exe[MAX_PATH], path[MAX_PATH], package[MAX_PATH];
    if (!GetDirectory(NULL, game)) return TRUE;
    _snwprintf(logPath, MAX_PATH, L"%lsHighFPS-loader.log", game);
    Log("BOOT: Workshop High FPS Loader 0.1.0");
    if (GetModuleHandleW(L"KotorPatcher.dll")) { Log("SKIP: another patch manager is already loaded"); return TRUE; }
    GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (!HashFile(exe, HFP_EXE_SHA256) || (DWORD)GetModuleHandleW(NULL) != 0x00400000) {
        Log("SKIP: unsupported or modified game executable"); return TRUE;
    }
    HMODULE steam = GetModuleHandleW(L"steam_api.dll");
    typedef int (__cdecl *GetUser)(void);
    typedef void* (__cdecl *GetUGC)(void);
    typedef unsigned (__cdecl *GetCount)(void*);
    typedef unsigned (__cdecl *GetItems)(void*, unsigned long long*, unsigned);
    typedef unsigned char (__cdecl *GetInstall)(void*, unsigned long long, unsigned long long*, char*, unsigned, unsigned char*);
    typedef unsigned char (__cdecl *GetUpdate)(void*, unsigned long long, unsigned char*, unsigned char*, unsigned long long*, unsigned long long*);
    GetUser user = steam ? (GetUser)GetProcAddress(steam, "SteamAPI_GetHSteamUser") : NULL;
    GetUGC ugc = steam ? (GetUGC)GetProcAddress(steam, "SteamUGC") : NULL;
    GetCount count = steam ? (GetCount)GetProcAddress(steam, "SteamAPI_ISteamUGC_GetNumSubscribedItems") : NULL;
    GetItems items = steam ? (GetItems)GetProcAddress(steam, "SteamAPI_ISteamUGC_GetSubscribedItems") : NULL;
    GetInstall install = steam ? (GetInstall)GetProcAddress(steam, "SteamAPI_ISteamUGC_GetItemInstallInfo") : NULL;
    GetUpdate update = steam ? (GetUpdate)GetProcAddress(steam, "SteamAPI_ISteamUGC_GetItemUpdateInfo") : NULL;
    if (!user || !ugc || !count || !items || !install || !update) { Log("SKIP: required legacy Steam exports unavailable"); return TRUE; }
    if (!user()) { Log("DEFER: wait for the game's first initialized Steam callback"); return FALSE; }
    void* service = ugc();
    if (!service) { Log("SKIP: Steam UGC interface unavailable"); return TRUE; }
    unsigned n = count(service);
    if (!n || n > 1000000) { Log("SKIP: no valid subscription list"); return TRUE; }
    unsigned long long wanted = _wcstoui64(WORKSHOP_ID, NULL, 10);
    unsigned long long* ids = HeapAlloc(GetProcessHeap(), 0, n * sizeof(*ids));
    if (!ids) return TRUE;
    unsigned got = items(service, ids, n);
    int subscribed = 0;
    for (unsigned i = 0; i < got && i < n; ++i) if (ids[i] == wanted) subscribed = 1;
    HeapFree(GetProcessHeap(), 0, ids);
    if (!subscribed) { Log("SKIP: item not subscribed"); return TRUE; }
    unsigned char legacy = 0, needsUpdate = 0, downloading = 0;
    unsigned long long bytes = 0, downloaded = 0, total = 0;
    char folder[MAX_PATH] = {0};
    if (!install(service, wanted, &bytes, folder, MAX_PATH, &legacy) || legacy ||
        !update(service, wanted, &needsUpdate, &downloading, &downloaded, &total) || needsUpdate || downloading) {
        Log("SKIP: item not installed or download unfinished"); return TRUE;
    }
    wchar_t installed[MAX_PATH];
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, folder, -1, installed, MAX_PATH)) return TRUE;
    _snwprintf(path, MAX_PATH, L"%ls\\native\\", installed);
    if (!GetFullPathNameW(path, MAX_PATH, package, NULL)) return TRUE;
    LoadPayload(package);
    return TRUE;
}

static void __cdecl SteamCallbacks(void) {
    originalCallbacks();
    int highFpsReady=InitOnceExecuteOnce(&patchOnce, PatchInit, NULL, NULL);
    int overlayReady=InitializeTextOverlay();
    if (highFpsReady && overlayReady && callbackSlot) {
        DWORD old, ignored;
        if (VirtualProtect((void*)callbackSlot, sizeof(LONG), PAGE_READWRITE, &old)) {
            InterlockedCompareExchange(callbackSlot, (LONG)originalCallbacks, (LONG)SteamCallbacks);
            VirtualProtect((void*)callbackSlot, sizeof(LONG), old, &ignored);
        }
    }
}

// Apply on the game's own thread after Steam initialization, never from DllMain
// or a background thread while game instructions could be running concurrently.
static void DeferUntilSteamCallback(void) {
    if(callbackSlot)return;
    unsigned char* image = (unsigned char*)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)image;
    IMAGE_NT_HEADERS32* nt = (IMAGE_NT_HEADERS32*)(image + dos->e_lfanew);
    IMAGE_IMPORT_DESCRIPTOR* imports = (void*)(image + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    for (; imports->Name; ++imports) {
        if (_stricmp((char*)image + imports->Name, "steam_api.dll")) continue;
        IMAGE_THUNK_DATA32* names = (void*)(image + imports->OriginalFirstThunk);
        IMAGE_THUNK_DATA32* slots = (void*)(image + imports->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            IMAGE_IMPORT_BY_NAME* name = (void*)(image + names->u1.AddressOfData);
            if (strcmp((char*)name->Name, "SteamAPI_RunCallbacks")) continue;
            DWORD old, ignored;
            originalCallbacks = (void*)slots->u1.Function;
            callbackSlot = (volatile LONG*)&slots->u1.Function;
            if (VirtualProtect((void*)callbackSlot, sizeof(LONG), PAGE_READWRITE, &old)) {
                InterlockedExchange(callbackSlot, (LONG)SteamCallbacks);
                VirtualProtect((void*)callbackSlot, sizeof(LONG), old, &ignored);
                Log("DEFER: Steam callback handoff installed");
            }
            return;
        }
    }
    Log("SKIP: cannot defer safely to Steam initialization");
}

static BOOL CALLBACK RealInit(PINIT_ONCE once, PVOID parameter, PVOID* context) {
    (void)once; (void)parameter; (void)context;
    wchar_t path[MAX_PATH];
    UINT n = GetSystemDirectoryW(path, MAX_PATH);
    if (n && n + 13 < MAX_PATH) {
        wcscat(path, L"\\dinput8.dll");
        realInput = LoadLibraryExW(path, NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    }
    return TRUE;
}

static FARPROC Real(const char* name) {
    InitOnceExecuteOnce(&realOnce, RealInit, NULL, NULL);
    return realInput ? GetProcAddress(realInput, name) : NULL;
}

HRESULT WINAPI DirectInput8Create(HINSTANCE instance, DWORD version, const GUID* iid, void** result, void* outer) {
    typedef HRESULT (WINAPI *Fn)(HINSTANCE, DWORD, const GUID*, void**, void*);
    Fn fn = (Fn)Real("DirectInput8Create");
    if (!fn) return E_FAIL;
#ifdef HFP_CURSOR_TRACE
    InitOnceExecuteOnce(&cursorTraceOnce, InstallCursorTrace, NULL, NULL);
#endif
    int highFpsReady=InitOnceExecuteOnce(&patchOnce, PatchInit, NULL, NULL);
    int overlayReady=InitializeTextOverlay();
    if (!highFpsReady || !overlayReady) DeferUntilSteamCallback();
    HRESULT status = fn(instance, version, iid, result, outer);
    ApplyBorderless();
    return status;
}
HRESULT WINAPI DllCanUnloadNow(void) {
    typedef HRESULT (WINAPI *Fn)(void); Fn fn = (Fn)Real("DllCanUnloadNow"); return fn ? fn() : S_FALSE;
}
HRESULT WINAPI DllGetClassObject(const GUID* clsid, const GUID* iid, void** result) {
    typedef HRESULT (WINAPI *Fn)(const GUID*, const GUID*, void**);
    Fn fn = (Fn)Real("DllGetClassObject"); return fn ? fn(clsid, iid, result) : E_FAIL;
}
HRESULT WINAPI DllRegisterServer(void) {
    typedef HRESULT (WINAPI *Fn)(void); Fn fn = (Fn)Real("DllRegisterServer"); return fn ? fn() : E_FAIL;
}
HRESULT WINAPI DllUnregisterServer(void) {
    typedef HRESULT (WINAPI *Fn)(void); Fn fn = (Fn)Real("DllUnregisterServer"); return fn ? fn() : E_FAIL;
}
#ifdef HFP_TEST
__declspec(dllexport) int __cdecl HfpTestLoad(const wchar_t* package) { return LoadPayload(package); }
__declspec(dllexport) int __cdecl HfpTestRollback(void) { return Rollback() && Preflight(); }
#endif
#include <stdint.h>
#include "message_buffer_fix.h"
#include "font_scale_fix.h"
#include "tlk_overlay_workshop.h"
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, void* reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) { selfModule = module; DisableThreadLibraryCalls(module); InitializeMessageBufferFix(); InitializeFontScaleFix(); }
    return TRUE;
}
