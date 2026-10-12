#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "message_buffer_fix.h"
int main(void) {
    BYTE* image=(BYTE*)VirtualAlloc(NULL,MESSAGE_PATCH_IMAGE_SIZE,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!image)return 1;
    IMAGE_DOS_HEADER* dos=(IMAGE_DOS_HEADER*)image;dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=256;
    IMAGE_NT_HEADERS32* nt=(IMAGE_NT_HEADERS32*)(image+256);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->FileHeader.TimeDateStamp=MESSAGE_PATCH_TIMESTAMP;nt->OptionalHeader.SizeOfImage=MESSAGE_PATCH_IMAGE_SIZE;
    const unsigned count=sizeof(messagePatches)/sizeof(messagePatches[0]);
    for(unsigned i=0;i<count;i++)memcpy(image+messagePatches[i].rva,messagePatches[i].oldBytes,messagePatches[i].size);
    /* Any signature conflict must cause zero partial writes. */
    image[messagePatches[count-1].rva]^=1;
    if(ApplyMessagePatchToImage(image)!=-3)return 2;
    for(unsigned i=0;i<count-1;i++)if(memcmp(image+messagePatches[i].rva,messagePatches[i].oldBytes,messagePatches[i].size))return 3;
    image[messagePatches[count-1].rva]^=1;
    if(ApplyMessagePatchToImage(image)!=(int)count)return 4;
    for(unsigned i=0;i<count;i++)if(memcmp(image+messagePatches[i].rva,messagePatches[i].newBytes,messagePatches[i].size))return 5;
    for(unsigned i=0;i<count;i++) {
        MEMORY_BASIC_INFORMATION m;
        if(!VirtualQuery(image+messagePatches[i].rva,&m,sizeof(m)) || m.Protect!=PAGE_READWRITE)return 7;
    }
    if(ApplyMessagePatchToImage(image)!=-3)return 6;
    VirtualFree(image,0,MEM_RELEASE);
    puts("PASS: all 126 signatures; conflict leaves image untouched; repeated patch rejected; page protection restored.");
    return 0;
}
