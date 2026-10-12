/* Optional process-start CNetLayer buffer expansion, never edits the EXE. */
typedef struct { DWORD rva, size; unsigned char oldBytes[16],newBytes[16]; } MessagePatch;
#include "message_buffer_patches.h"
typedef struct { BYTE* address; DWORD oldProtection; } MessagePage;

/* No allocation, DLL loads, callbacks or game object access under loader lock. */
static int ApplyMessagePatchToImage(BYTE* image) {
    IMAGE_DOS_HEADER* dos=(IMAGE_DOS_HEADER*)image;
    if (!image || dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>4096) return -1;
    IMAGE_NT_HEADERS32* nt=(IMAGE_NT_HEADERS32*)(image+dos->e_lfanew);
    if (nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386 ||
        nt->FileHeader.TimeDateStamp!=MESSAGE_PATCH_TIMESTAMP || nt->OptionalHeader.SizeOfImage!=MESSAGE_PATCH_IMAGE_SIZE) return -2;
    MessagePage pages[256]; unsigned pageCount=0;
    const unsigned count=sizeof(messagePatches)/sizeof(messagePatches[0]);
    for (unsigned i=0;i<count;i++) {
        const MessagePatch* p=&messagePatches[i];
        if (p->size>16 || p->rva+p->size>nt->OptionalHeader.SizeOfImage || memcmp(image+p->rva,p->oldBytes,p->size)) return -3;
        uintptr_t start=(uintptr_t)(image+p->rva)&~(uintptr_t)4095;
        uintptr_t end=(uintptr_t)(image+p->rva+p->size-1)&~(uintptr_t)4095;
        for (uintptr_t a=start;a<=end;a+=4096) {
            unsigned j;for(j=0;j<pageCount;j++) if(pages[j].address==(BYTE*)a) break;
            if(j==pageCount) { if(pageCount==256) return -4; pages[pageCount++].address=(BYTE*)a; }
        }
    }
    unsigned changed=0;DWORD ignored;
    for (;changed<pageCount;changed++) {
        if(!VirtualProtect(pages[changed].address,4096,PAGE_EXECUTE_READWRITE,&pages[changed].oldProtection)) {
            for(unsigned j=0;j<changed;j++) VirtualProtect(pages[j].address,4096,pages[j].oldProtection,&ignored);
            return -5;
        }
    }
    for(unsigned i=0;i<count;i++) memcpy(image+messagePatches[i].rva,messagePatches[i].newBytes,messagePatches[i].size);
    FlushInstructionCache(GetCurrentProcess(),image,nt->OptionalHeader.SizeOfImage);
    int status=(int)count;
    for(unsigned j=0;j<pageCount;j++) if(!VirtualProtect(pages[j].address,4096,pages[j].oldProtection,&ignored)) status=-6;
    return status;
}

static void InitializeMessageBufferFix(void) {
    wchar_t gamePath[MAX_PATH];DWORD n=GetModuleFileNameW(NULL,gamePath,MAX_PATH);
    if(!n || n>=MAX_PATH) return;
    wchar_t* slash=wcsrchr(gamePath,L'\\');if(!slash) return;
    if(_wcsicmp(slash+1,L"swkotor2.exe")) return;
    slash[1]=0;wchar_t ini[MAX_PATH],log[MAX_PATH];
    if(wcslen(gamePath)+32>=MAX_PATH) return;
    wcscpy(ini,gamePath);wcscat(ini,L"swkotor2.ini");
    /* Explicit toggle; default off. Applies before the two native allocations. */
    if(!GetPrivateProfileIntW(L"Chinese Text Fix",L"MessageBufferFix",0,ini)) return;
    int status=ApplyMessagePatchToImage((BYTE*)GetModuleHandleW(NULL));
    wcscpy(log,gamePath);wcscat(log,L"MessageBuffer-fix.log");
    HANDLE f=CreateFileW(log,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(f!=INVALID_HANDLE_VALUE) {
        char text[160];DWORD written;int size=snprintf(text,sizeof(text),"MessageBufferFix: status=%d; patches=126; half=4194304; total=8388608; process-start only\r\n",status);
        WriteFile(f,text,(DWORD)size,&written,NULL);CloseHandle(f);
    }
}
