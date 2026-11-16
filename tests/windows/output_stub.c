#include <windows.h>
#include <stdio.h>
int main(void){char data[4096];for(int i=0;i<4096;i++)data[i]='x';for(int i=0;i<2304;i++)fwrite(data,1,sizeof(data),stdout);fflush(stdout);Sleep(30000);return 0;}
