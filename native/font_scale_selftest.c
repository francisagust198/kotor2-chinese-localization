#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "font_scale_fix.h"
static int __attribute__((naked,used)) InvokeMeasure(void* frame,int mode,double input) {
    __asm__ volatile("pushl %ebp\n\tmovl 8(%esp),%ebp\n\tfldl 16(%esp)\n\tcmpl $1,12(%esp)\n\tje 1f\n\tcall _FontScaleInitial\n\tjmp 2f\n\t1: call _FontScaleAccumulate\n\t2: popl %ebp\n\tret");
}
#define CHECK(expr) do {if(!(expr)){printf("FAIL line %d\n",__LINE__);return 1;}} while(0)
int main(void) {
    unsigned char frameStorage[128]={0},font[64]={0},object[96]={0};
    unsigned char* frame=frameStorage+100;
    float upper[768]={0},lower[768]={0};
    *(float**)(font+0x18)=upper;*(float**)(font+0x24)=lower;*(float*)(font+0xc)=10.24f;
    for(unsigned i=129;i<=192;i++)lower[i*3]=1.5f/1024;
    lower[250*3]=-1.5f/1024;lower[128*3]=lower[193*3]=1.0f/1024;
    lower[252*3]=-16.5f/1024;lower[249*3]=16.5f/1024;
    lower['A'*3]=8.0f/1024;
    *(void**)(frame-0x1c)=font;*(void**)(frame-0x60)=object;
    fontScaleTls=TlsAlloc();CHECK(fontScaleTls!=TLS_OUT_OF_INDEXES);
    unsigned char stream[200000];unsigned length=0;
    for(unsigned glyph=0;glyph<96;glyph++) {
        for(unsigned column=0;column<16;column++) {
            /* Vary stroke counts without changing the glyph's true advance. */
            for(unsigned row=0;row<(glyph%9)+1;row++){stream[length++]=(unsigned char)(129+row*4);stream[length++]=250;}
            stream[length++]=(column%2)?193:128;
        }
        stream[length++]=252;stream[length++]=249;stream[length++]=32;
    }
    const float scales[]={2.0f/3.0f,5.0f/6.0f,1.0f,4.0f/3.0f,1.5f,2.0f};
    unsigned checks=0;
    for(unsigned s=0;s<sizeof(scales)/sizeof(scales[0]);s++) {
        *(float*)(object+0x54)=scales[s];*(void**)(frame-0x14)=stream;
        int total=0;unsigned completed=0;
        for(unsigned i=0;i<length;i++) {
            *(void**)(frame-0xc)=stream+i;*(int*)(frame-0x2c)=total;
            double native=FontRawWidth(font,stream[i])*(double)scales[s]*100+(i?0.25:0);
            int result=InvokeMeasure(frame,i?1:0,native);total=i?total+result:result;
            if(stream[i]==32) {completed++;CHECK(abs(total-(int)(completed*16*(double)scales[s]+0.25))<=1);checks++;}
        }
        CHECK(completed==96);
        /* Reusing the frame must not leak a previous line's fractional part. */
        *(void**)(frame-0xc)=stream;CHECK(InvokeMeasure(frame,0,12345.75)==(int)(FontRawWidth(font,stream[0])*scales[s]*100+0.25));
    }
    /* Non-composite fonts retain the original conversion, regardless of scale. */
    lower[252*3]=8.0f/1024;CHECK(InvokeMeasure(frame,1,-1.75)==-1);lower[252*3]=-16.5f/1024;
    BYTE* image=(BYTE*)VirtualAlloc(NULL,7049216,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(image);
    IMAGE_DOS_HEADER* dos=(IMAGE_DOS_HEADER*)image;dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=128;
    IMAGE_NT_HEADERS32* nt=(IMAGE_NT_HEADERS32*)(image+128);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->FileHeader.TimeDateStamp=1443037277;nt->OptionalHeader.SizeOfImage=7049216;
    DWORD sites[]={0x7b020,0x7b238,0x7b4e2};
    for(unsigned i=0;i<3;i++){image[sites[i]]=0xe8;int32_t d=0x51c860-sites[i]-5;memcpy(image+sites[i]+1,&d,4);}
    image[sites[1]]=0x90;CHECK(ApplyFontScaleFix(image)==-3);CHECK(image[sites[0]]==0xe8);image[sites[1]]=0xe8;
    DWORD old;CHECK(VirtualProtect(image+0x7b000,4096,PAGE_EXECUTE_READ,&old));
    CHECK(ApplyFontScaleFix(image)==3);MEMORY_BASIC_INFORMATION info;CHECK(VirtualQuery(image+sites[0],&info,sizeof(info)));CHECK(info.Protect==PAGE_EXECUTE_READ);
    CHECK(ApplyFontScaleFix(image)==-3);VirtualFree(image,0,MEM_RELEASE);
    printf("PASS: %u complete glyph boundaries at 6 scales, x87 wrapper ABI, restart, ASCII fallback, 3-site preflight/conflict and page restoration.\n",checks);
    return 0;
}
