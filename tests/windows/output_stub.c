#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char**argv){
#ifdef SLOW_ONLY
const char *path=getenv("AMUA_TEST_SNAPSHOT_TRACK");if(path&&argc>2){FILE *track=fopen(path,"w");if(track){fprintf(track,"%s",argv[argc-2]);fclose(track);}}
#else
char data[4096];for(int i=0;i<4096;i++)data[i]='x';for(int i=0;i<2304;i++)fwrite(data,1,sizeof(data),stdout);fflush(stdout);
#endif
Sleep(30000);return 0;}
