/* io.h - the host interface of y1cc.c (2026-09-24).

   y1cc.c calls nothing else outside itself: no libc, no syscalls. host_io.c implements this on the Mac with stdio;
   target_io.c implements it for Y1/OS (the file syscalls, os/lib_fs.c) so that the same y1cc.c can one day run on
   the machine. Everything is plain ints and char buffers, in the C subset y1cc accepts: bytes are 0..255, "none"
   is 0 and the end of a file is 256, never a negative number.

   The command line
     io_argc()                  the number of command-line words after the program name
     io_arg(i, buf, max)        word i (0 = the first after the program name) into buf, NUL-terminated, at most
                                max - 1 characters
   Source files
     io_open(path)              open a file for reading: a handle (1..), or 0 when it cannot be read
     io_getc(h)                 the next byte 0..255, or 256 at the end of the file
     io_close(h)
     io_skip(h, n)              n bytes read past (2026-09-25: the passes skip whole function bodies)
     io_find(name, from, out, max)   #include "name" written in file `from`: look beside `from`, then in the
                                compiler's library directory (software/compiler/lib on the host); 1 = found, with
                                the file's canonical path (the same file always gets the same text) in out
   The output: three sections, concatenated in the order 0, 1, 2 when the compile succeeded
     io_create(path)            the output file the sections will go to; 1 = fine (the host writes it at io_finish,
                                so a failed compile leaves no file, as y1cc.py does)
     io_put(s, c)               append byte c to section s (0 code, 1 data, 2 uninitialised data)
     io_finish()                write sections 0, 1, 2 to the output; 1 = done
   Intermediate files (the passes of the multi-pass compiler, 2026-09-24): one file open for writing at a time, as
   Y1/OS allows
     io_wopen(path)             create path for writing (replacing a file of that name); 1 = fine
     io_wput(c)                 append byte c to it
     io_wputs(s)                append the NUL-terminated string s to it, not its NUL (2026-09-25: cc9's lines)
     io_wclose()                close it
   The console and the rest
     io_out(c)                  one byte to standard output (the -l summary)
     io_fail(msg)               msg and a newline to standard error, then stop with exit status 1 (does not return
                                on the host)
     io_date(buf)               the date and time as "YYYY-MM-DD HH:MM" (17 bytes with the NUL) for the header
     io_done()                  stop now, successfully (exit status 0): a pass that has written a deferred error
     io_lib(name, out, max)     the path of a file in the compiler's library directory (cc9 reads the runtime
                                helpers from lib/y1ccrt.txt) */
int io_argc(void);
void io_arg(int i, char *buf, int max);
int io_open(char *path);
int io_getc(int h);
void io_close(int h);
void io_skip(int h, int n);
int io_find(char *name, char *from, char *out, int max);
int io_create(char *path);
void io_put(int s, int c);
int io_finish(void);
void io_out(int c);
void io_fail(char *msg);
void io_date(char *buf);
int io_wopen(char *path);
void io_wput(int c);
void io_wputs(char *s);
void io_wclose(void);
void io_done(void);
void io_lib(char *name, char *out, int max);
