#import <Cocoa/Cocoa.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <spawn.h>
#include <sys/wait.h>
extern char **environ;

@interface AmuaDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic) pid_t javaPID;
@property(nonatomic, copy) NSString *bridge;
@property(nonatomic, strong) dispatch_source_t monitor;
@end

@implementation AmuaDelegate
- (void)activateChild {
    if(self.javaPID>0) {
        NSRunningApplication *child=[NSRunningApplication runningApplicationWithProcessIdentifier:self.javaPID];
        [child activateWithOptions:NSApplicationActivateIgnoringOtherApps];
    }
}
- (void)send:(NSString *)method files:(NSArray *)files {
    NSDictionary *request = @{@"method":method, @"params":@{@"files":files ?: @[]},
        @"token":[NSString stringWithContentsOfFile:[[self.bridge stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"bridge.token"] encoding:NSUTF8StringEncoding error:nil] ?: @"",
                @"deadline":@([[NSDate date] timeIntervalSince1970]+30)};
    NSData *json = [NSJSONSerialization dataWithJSONObject:request options:0 error:nil];
    NSString *name = [[NSUUID UUID].UUIDString stringByAppendingString:@".request.json"];
    [json writeToFile:[self.bridge stringByAppendingPathComponent:name] atomically:YES];
}
- (void)application:(NSApplication *)sender openFiles:(NSArray<NSString *> *)filenames {
    [self activateChild];
    [self send:@"activate" files:filenames];
    [sender replyToOpenOrPrint:NSApplicationDelegateReplySuccess];
}
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    [self activateChild];[self send:@"activate" files:@[]];return YES;
}
- (BOOL)applicationShouldOpenUntitledFile:(NSApplication *)sender {return NO;}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (self.javaPID == 0) return NSTerminateNow;
    [self send:@"quit" files:@[]];return NSTerminateCancel;
}
@end

// Keep the bundle's native process alive to receive LaunchServices file events.
// Java owns its normal window/Dock icon; this accessory process routes events.
int main(int argc, char **argv) {
    @autoreleasepool {
        umask(0077);
        NSString *resources = [[NSBundle mainBundle] resourcePath];
        NSString *support = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/Amua-v3.2.4"];
        NSError *error = nil;
        if (![[NSFileManager defaultManager] createDirectoryAtPath:support
                  withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions:@0700} error:&error]) {
            fprintf(stderr, "Amua: %s\n", error.localizedDescription.UTF8String);
            return 1;
        }
        NSString *bridge = [support stringByAppendingPathComponent:@"bridge"];
        [[NSFileManager defaultManager] createDirectoryAtPath:bridge withIntermediateDirectories:YES
                   attributes:@{NSFilePosixPermissions:@0700} error:&error];
        int lock = open([[support stringByAppendingPathComponent:@"app.lock"] fileSystemRepresentation], O_CREAT|O_RDWR, 0600);
        if (lock < 0) return 1;
        if (flock(lock, LOCK_EX|LOCK_NB) != 0) {
            // A second launch brings the running window forward using its own bridge.
            NSMutableArray *files = [NSMutableArray array];
            for (int i=1;i<argc;i++) {
                NSString *p = [NSString stringWithUTF8String:argv[i]];
                if ([p.pathExtension.lowercaseString isEqualToString:@"amua"]) [files addObject:p];
            }
            NSDictionary *request = @{@"method":@"activate", @"params":@{@"files":files},
        @"token":[NSString stringWithContentsOfFile:[support stringByAppendingPathComponent:@"bridge.token"] encoding:NSUTF8StringEncoding error:nil] ?: @"",
                @"deadline":@([[NSDate date] timeIntervalSince1970]+30)};
            NSData *json = [NSJSONSerialization dataWithJSONObject:request options:0 error:nil];
            NSString *name = [[NSUUID UUID].UUIDString stringByAppendingString:@".request.json"];
            [json writeToFile:[bridge stringByAppendingPathComponent:name] atomically:YES];
            return 0;
        }
        [[NSUUID UUID].UUIDString writeToFile:[support stringByAppendingPathComponent:@"bridge.token"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
        fcntl(lock, F_SETFD, FD_CLOEXEC); // The native parent owns the instance lock.
        chdir(support.fileSystemRepresentation); // Recent files/settings stay out of the bundle.
        NSString *logPath = [support stringByAppendingPathComponent:@"Amua.log"];
        NSDictionary *attr = [[NSFileManager defaultManager] attributesOfItemAtPath:logPath error:nil];
        if ([attr fileSize] > 2*1024*1024) {
            NSString *oldLog = [support stringByAppendingPathComponent:@"Amua.previous.log"];
            [[NSFileManager defaultManager] removeItemAtPath:oldLog error:nil];
            [[NSFileManager defaultManager] moveItemAtPath:logPath toPath:oldLog error:nil];
        }
        int log = open(logPath.fileSystemRepresentation, O_CREAT|O_WRONLY|O_APPEND, 0600);
        if (log >= 0) {dup2(log, STDOUT_FILENO); dup2(log, STDERR_FILENO); close(log);}
        NSString *java = [resources stringByAppendingPathComponent:@"runtime/bin/java"];
        NSString *jar = [resources stringByAppendingPathComponent:@"Amua_0.3.6.jar"];
        NSMutableArray<NSString *> *args = [NSMutableArray arrayWithArray:@[
            java, @"-Xms64m", @"-Xmx2g", @"-XX:+UseG1GC", @"-XX:MaxGCPauseMillis=100",
            @"-Xdock:name=Amua (ReyJay) V 3.2.4", [@"-Xdock:icon=" stringByAppendingString:[resources stringByAppendingPathComponent:@"Amua.icns"]],
            @"-Dapple.laf.useScreenMenuBar=true", @"-Dcom.apple.macos.useScreenMenuBar=true",
            @"-Dcom.apple.mrj.application.apple.menu.about.name=Amua", @"-Dapple.awt.application.name=Amua",
            @"-Dsun.net.client.defaultConnectTimeout=4000", @"-Dsun.net.client.defaultReadTimeout=4000",
            [@"-Damua.support=" stringByAppendingString:support],
            [@"-Damua.resources=" stringByAppendingString:resources],
            @"-cp", jar, @"jdk.nashorn.tools.Shell",
            [resources stringByAppendingPathComponent:@"bootstrap.js"], @"--"
        ]];
        for (int i=1; i<argc; i++) {
            NSString *p = [NSString stringWithUTF8String:argv[i]];
            if (![p hasPrefix:@"-psn_"]) [args addObject:p];
        }
        char **nativeArgs = calloc(args.count+1, sizeof(char *));
        for (NSUInteger i=0;i<args.count;i++) nativeArgs[i] = strdup(args[i].UTF8String);
        NSApplication *application=[NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyAccessory];
        AmuaDelegate *delegate=[AmuaDelegate new];delegate.bridge=bridge;
        application.delegate=delegate;
        pid_t child=0;
        NSDictionary *hostEnv=NSProcessInfo.processInfo.environment;
        NSMutableArray<NSString *> *envItems=[NSMutableArray arrayWithObjects:@"PATH=/usr/bin:/bin:/usr/sbin:/sbin", @"PYTHONDONTWRITEBYTECODE=1", nil];
        for(NSString *key in @[@"HOME",@"USER",@"LOGNAME",@"TMPDIR",@"LANG",@"LC_CTYPE"]) {
            NSString *value=hostEnv[key];if(value) [envItems addObject:[NSString stringWithFormat:@"%@=%@",key,value]];
        }
        char **childEnv=calloc(envItems.count+1,sizeof(char *));
        for(NSUInteger i=0;i<envItems.count;i++) childEnv[i]=strdup(envItems[i].UTF8String);
        int spawned=posix_spawn(&child,java.fileSystemRepresentation,NULL,NULL,nativeArgs,childEnv);
        for(NSUInteger i=0;i<envItems.count;i++) free(childEnv[i]);free(childEnv);
        for(NSUInteger i=0;i<args.count;i++) free(nativeArgs[i]);free(nativeArgs);
        if(spawned!=0) {
            fprintf(stderr,"Amua could not launch its bundled runtime: %s\n",strerror(spawned));return 1;
        }
        delegate.javaPID=child;
        delegate.monitor=dispatch_source_create(DISPATCH_SOURCE_TYPE_PROC,child,DISPATCH_PROC_EXIT,dispatch_get_main_queue());
        dispatch_source_set_event_handler(delegate.monitor, ^{
            int status;waitpid(child,&status,0);delegate.javaPID=0;[NSApp terminate:nil];
        });
        dispatch_resume(delegate.monitor);
        [application run];
        return 0;
    }
}
