#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <shellapi.h>
#include <stdlib.h>
#include <wchar.h>
static wchar_t command[32768];static size_t used;
static int put(wchar_t ch){if(used>=32766)return 0;command[used++]=ch;command[used]=0;return 1;}
static int quoted(const wchar_t *value){
 if(!put(L'"'))return 0;size_t slash=0;
 for(;*value;value++){
  if(*value==L'\\'){slash++;continue;}
  size_t count=(*value==L'"')?slash*2+1:slash;
  while(count--)if(!put(L'\\'))return 0;slash=0;if(!put(*value))return 0;
 }
 while(slash--)if(!put(L'\\')||!put(L'\\'))return 0;
 return put(L'"')&&put(L' ');
}
static int error(const wchar_t *message){MessageBoxW(NULL,message,L"Amua 3.2.4 for Windows",MB_OK|MB_ICONERROR);return 1;}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR ignored,int show){
 wchar_t folder[32768],python[32768],script[32768];
 DWORD n=GetModuleFileNameW(NULL,folder,32768);if(!n||n>=32000)return error(L"Move the extracted Amua folder to a shorter local path.");
 // Ignore host Python customizations before starting the bundled supervisor.
 SetEnvironmentVariableW(L"PYTHONPATH",NULL);SetEnvironmentVariableW(L"PYTHONHOME",NULL);
 SetEnvironmentVariableW(L"PYTHONSTARTUP",NULL);SetEnvironmentVariableW(L"PYTHONINSPECT",NULL);
 SetEnvironmentVariableW(L"PYTHONUTF8",L"1");SetEnvironmentVariableW(L"PYTHONIOENCODING",L"utf-8");SetEnvironmentVariableW(L"PYTHONNOUSERSITE",L"1");SetEnvironmentVariableW(L"PYTHONDONTWRITEBYTECODE",L"1");
 wchar_t *last=wcsrchr(folder,L'\\');if(!last)return 1;*last=0;
 if(swprintf(python,32768,L"%ls\\Resources\\python\\pythonw.exe",folder)<0||swprintf(script,32768,L"%ls\\launch.py",folder)<0)return 1;
 if(GetFileAttributesW(python)==INVALID_FILE_ATTRIBUTES||GetFileAttributesW(script)==INVALID_FILE_ATTRIBUTES)return error(L"Extract the complete ZIP before opening Amua.exe. Its bundled runtime is missing.");
 if(!quoted(python)||!quoted(script))return error(L"The application path is too long.");
 int argc=0;LPWSTR *argv=CommandLineToArgvW(GetCommandLineW(),&argc);if(!argv)return 1;
 for(int i=1;i<argc;i++)if(!quoted(argv[i])){LocalFree(argv);return error(L"The file argument is too long.");}LocalFree(argv);
 HANDLE job=CreateJobObjectW(NULL,NULL);if(!job)return error(L"Amua could not create its process supervisor.");
 JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={0};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
 if(!SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits))){CloseHandle(job);return error(L"Amua could not initialize its process supervisor.");}
 STARTUPINFOW startup={0};startup.cb=sizeof(startup);PROCESS_INFORMATION child={0};
 if(!CreateProcessW(python,command,NULL,NULL,FALSE,CREATE_UNICODE_ENVIRONMENT|CREATE_NO_WINDOW|CREATE_SUSPENDED,NULL,folder,&startup,&child)){CloseHandle(job);return error(L"Amua could not start its bundled Python runtime.");}
 if(!AssignProcessToJobObject(job,child.hProcess)){TerminateProcess(child.hProcess,1);CloseHandle(child.hThread);CloseHandle(child.hProcess);CloseHandle(job);return error(L"Amua could not supervise its application processes.");}
 ResumeThread(child.hThread);CloseHandle(child.hThread);WaitForSingleObject(child.hProcess,INFINITE);DWORD status=1;GetExitCodeProcess(child.hProcess,&status);CloseHandle(child.hProcess);CloseHandle(job);return (int)status;
}
