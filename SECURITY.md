# Security

OCforge downloads and runs third-party kexts and tools (OpenCore itself,
SSDTTime, acidanthera/community kexts, `acpidump.exe` on Windows), reads and
writes ACPI tables, and can format/write a USB device (`--usb`, always with a
confirmation prompt first). That's real surface for something to go wrong —
if you find a way to make it do something it shouldn't, please report it
privately rather than as a public issue.

## Reporting a vulnerability

Use GitHub's private reporting for this repo:
[Report a vulnerability](https://github.com/kevinisgoated24-spec/OCforge/security/advisories/new)
(Security tab → "Report a vulnerability"). That opens a draft advisory only
the maintainers can see until it's resolved.

If that's not workable for some reason, open a regular issue asking to be
pointed to another contact — just don't post exploit details there.

## What's in scope

- Anything that lets a downloaded EFI, kext, or SSDT differ from what a
  trusted upstream (Acidanthera, corpnewt, Dortania) actually published —
  a broken hash/signature check, a spoofable download source, etc.
- Anything that runs unintended code on the machine `ocforge` is running on
  (the build host), not the eventual Hackintosh target.
- Credential or token handling — though the CLI itself never holds one;
  see `discordbot/README.md` for that component's separate token handling.

## What's out of scope

- The Hackintosh install itself being "insecure" in the sense of running
  unsigned kexts, disabling SIP-adjacent quirks, etc. — that's the nature of
  Hackintosh, not a bug in this tool.
- Issues in upstream projects OCforge fetches (OpenCore, individual kexts,
  SSDTTime, gibMacOS, UnPlugged) — report those to their own repos.
