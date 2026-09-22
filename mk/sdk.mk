# Shared by the C tools' Makefiles (2026-09-22). macOS 27's Command Line Tools SDK (MacOSX.sdk -> 27.0) carries
# tbd files the Xcode 17 linker rejects ("tapi error: malformed file ... unknown architecture arm64e.x1"), so every
# link fails. If a trivial link fails with the default SDK, fall back to the newest older SDK that is installed.
SDKFLAGS := $(shell t=$$(mktemp -d); printf 'int main(void){return 0;}\n' > $$t/p.c; \
  if $(CC) $$t/p.c -o $$t/p > /dev/null 2>&1; then :; else \
    for s in /Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk /Library/Developer/CommandLineTools/SDKs/MacOSX26.sdk; do \
      [ -d $$s ] && { echo -isysroot $$s; break; }; done; fi; rm -rf $$t)
