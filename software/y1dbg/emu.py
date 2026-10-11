# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The connection to the emulator: y1ucemu -D started as a child process, one TCP connection on 127.0.0.1.

A command is one line; the reply is one line of JSON (software/ucemu/y1ucemu.c, "the debug server"). The emulator
exits when the connection closes, so closing this object (or this process ending, however it ends) leaves nothing
running; close() also waits for the process and kills it if it does not go.
"""
import json, os, re, socket, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EXE = os.path.join(ROOT, "software/ucemu/y1ucemu")


class EmulatorError(Exception):
    pass


class Emulator:
    def __init__(self, args=("-m",), exe=EXE, log=None):
        """args: y1ucemu's own options (-m, -f FILE, -c DISK, -u HEX, -N ...); log: a file for its stderr (None =
        inherit, e.g. the -w fight list)"""
        if not os.path.exists(exe):
            raise EmulatorError("%s is not built (make -C software/ucemu)" % exe)
        self.p = subprocess.Popen([exe, "-D", "0"] + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=log)
        line = self.p.stdout.readline().decode("latin1")
        self.p.stdout.close()
        m = re.search(r"port (\d+)", line)
        if not m:
            self.p.kill(); self.p.wait()
            raise EmulatorError("y1ucemu did not start its debug server: %r" % line.strip())
        self.port = int(m.group(1))
        self.sock = socket.create_connection(("127.0.0.1", self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.rf = self.sock.makefile("rb")
        self.status = {}

    def cmd(self, line):
        """send one command, return its reply (a dict); the status fields are kept in self.status"""
        if "\n" in line:
            raise EmulatorError("one line per command")
        try:
            self.sock.sendall(line.encode("latin1") + b"\n")
            reply = self.rf.readline()
        except OSError as e:
            raise EmulatorError("the emulator went away (%s)" % e)
        if not reply:
            raise EmulatorError("the emulator went away")
        r = json.loads(reply)
        self.status = {k: r[k] for k in ("state", "reason", "pc", "step", "instr", "steps", "clocks") if k in r}
        return r

    def ok(self, line):
        """cmd(), raising the emulator's error"""
        r = self.cmd(line)
        if not r.get("ok"):
            raise EmulatorError(r.get("error", "failed"))
        return r

    def mem(self, addr, n):
        return bytes.fromhex(self.ok("mem %X %d" % (addr & 0xFFFF, n))["hex"])

    def alive(self):
        return self.p.poll() is None

    def close(self):
        try:
            if self.alive():
                self.sock.sendall(b"quit\n"); self.rf.readline()
        except OSError:
            pass
        for f in (self.rf, self.sock):
            try: f.close()
            except OSError: pass
        try:
            self.p.wait(3)
        except subprocess.TimeoutExpired:
            self.p.kill(); self.p.wait()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
