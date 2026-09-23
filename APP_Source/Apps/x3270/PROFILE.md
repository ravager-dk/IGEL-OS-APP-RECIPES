# Configure x3270 through a UMS profile

Available in recipe **4.5.6+1.7**, based on x3270 **4.5ga6**. This extends the
community recipe without changing its `x3270.tar.bz2` binary input, service,
font directory or persistent `/userhome/.config/x3270` directory.

## Enable the profile settings

1. Build/sign the updated recipe ZIP through App Creator Portal, supplying the
   existing **4.5ga6** `x3270.tar.bz2` when prompted. The older Debian 4.1 payload
   from a separate recipe is not compatible with this recipe's layout.
2. Import the signed app into UMS and select the new version in the profile.
3. In Advanced Setup, select **x3270 > Connection > Configuration source >
   UMS profile** and activate that parameter. Activate/set the desired fields.
4. Configure the shortcut/autostart behavior under **Session**, assign the
   profile and synchronize the endpoint. Start/restart x3270 to apply changes.

The default configuration source is **Local / application defaults**, which
preserves normal x3270 startup. Other new fields are ignored in that mode.
Changing a profile does not terminate an active terminal connection.

There is one x3270 session per endpoint. Profiles can select different hosts
for different device groups. Multiple profiles on the same endpoint follow UMS
parameter precedence; they do not create multiple independent terminal sessions.

## Profile fields

| Field | Control / default | Behavior |
|---|---|---|
| Configuration source | Dropdown: Local | Local startup or UMS profile settings |
| Server hostname or IP | String: empty | Host only, including IPv4/IPv6. No URL, LU prefix or port. Empty opens the GUI |
| Server port | Integer: 23 | Range 1–65535, enforced by launcher |
| Connection mode | Dropdown: Automatic | Automatic (STARTTLS if offered), Direct TLS, Plain TN3270 |
| LU name | String: empty | Optional single logical unit / terminal ID, not a login name |
| Enable TN3270E | Checkbox: on | Off adds the `N:` connection prefix |
| On disconnect | Dropdown: Keep window open | Keep open, reconnect, or exit; last two require a server |
| Verify server certificate | Checkbox: on | TLS certificate chain and hostname verification |
| CA certificate file (PEM) | Path string: empty | Optional absolute path to a readable CA bundle; otherwise platform defaults |
| Terminal model | Dropdown: 3279-4 | 3278/3279 models 2–5; labels show dimensions and monochrome/color |
| Extended data stream | Checkbox: on | Native `extendedDataStream` resource; controls extended terminal indication |
| Host EBCDIC code page | Dropdown: bracket | 32 single-byte code pages from 4.5ga6, including cp1123 and cp1158 |
| Terminal font | Dropdown: 3270 | 17 fonts installed by x3270 4.5ga6 |
| Show on-screen keypad | Checkbox: off | Display keypad at startup |
| Custom keymap file | Path string: empty | Absolute endpoint path to an x3270 X resource file |
| Keymap resource name | String: ums | Name after `x3270.keymap.` in the file |

Changing connection mode does not change the port: set the actual TLS listener
port explicitly (often 992). Automatic STARTTLS permits plaintext if the server
does not negotiate TLS. Direct TLS uses `L:` and requires a TLS listener. These
connection prefixes apply to the initial configured host, not arbitrary hosts
subsequently entered through the GUI. DBCS options are omitted because this
recipe does not configure dedicated DBCS fonts.

The launcher validates values before opening the emulator. Invalid choices,
ports outside the range, malformed host/LU values and unreadable files fail
with a message on stderr and in the system log (`x3270-igel`). Profile values
are passed as quoted arguments, never evaluated as shell commands.

## Deploy a keymap file

Use [`examples/company-keymap.xrm`](examples/company-keymap.xrm) as a starting
point. It extends the built-in base map with Right Ctrl = Enter and Ctrl+F1 =
PF13:

```text
x3270.keymap.ums: \
    <Key>Control_R: Enter() \n\
    Ctrl<Key>F1: PF(13)
```

The literal `\n` and continuation backslashes are significant. This is an
**x3270 X resource file**, not a c3270/wc3270 plain translations file.

1. In **UMS Web App > Configuration > Files**, upload the `.xrm` file with
   **Classification = Undefined**.
2. Set **Device file location** to `/wfs/x3270/` (a directory ending in `/`).
   Use root ownership and permissions that allow the session user to read it,
   for example `0644`. No execute permission is needed.
3. Assign it to the same device/device directory as the profile. Alternatively,
   attach it to the profile through **Contained Files** where available, or
   use file-to-profile assignment in the UMS Console.
4. Set **Custom keymap file** to `/wfs/x3270/company-keymap.xrm` and **Keymap
   resource name** to `ums`. Use the actual deployed filename if UMS renamed it.
5. Synchronize file and profile before launching x3270. If autostart runs before
   file deployment completes, relaunch after the file arrives.

The filepath is separate from UMS file assignment; entering it does not upload
or transfer the file. The file must be readable, no larger than 64 KiB, and
contain `x3270.keymap.NAME:`. Names start with a letter and contain only letters,
digits, underscores or hyphens; `base` is reserved. Optional `.nvt`/`.3270`
resources can accompany the primary definition. Blank filepath uses the base
map. Restart the terminal after updating the file; no app rebuild is needed.

x3270's `-keymap` accepts a **name**, not an arbitrary filepath. The launcher
reads the file into `X3270RDB` and selects that name. It does not modify the
X server's global resource database. Resource files are administrator-managed
and can contain additional x3270 settings; keep keymap files focused on keys.
Explicit profile arguments override corresponding file resources.

A PEM CA bundle can be distributed by the same file-assignment mechanism and
referenced by **CA certificate file**.

## Local settings and persistence

Local mode invokes the existing `/services/x3270/usr/local/bin/x3270` and lets
x3270 load its normal local settings. Its existing `.x3270connect` persistence
link is retained. Manual command-line arguments are accepted in Local mode.

UMS mode bypasses automatic `.x3270pro` loading and rejects command-line
connection overrides. `-v` remains available for diagnostics. UMS mode is a
startup configuration, not a kiosk restriction on x3270's interactive menus.
The existing install service and font registration remain in use. Files
assigned through UMS are managed independently of the app.

## Maintainer checks

From the repository root:

```sh
python3 utils/x3270/render_config.py
python3 utils/x3270/test_recipe.py
python3 utils/x3270/package.py
python3 utils/x3270/package.py --check
```

`settings.json` under `utils/x3270/` defines control types, defaults and choices.
Keep the launcher and its tests in sync when changing those definitions. The
package helper rebuilds **only** `APP_Packages/Apps/x3270_community.zip` and checks
its content and executable permissions against the recipe source.

Validated locally: metadata and shell syntax; all dropdown/checkbox values;
argument construction; missing-file handling; local-mode compatibility; and
ZIP/source parity. The exact 4.5ga6 source was inspected for option names,
code pages, fonts and keymap resource loading. This update has **not** been
built with the IGEL SDK/portal or exercised in UMS/on an IGEL endpoint. Verify
those paths, file deployment, TLS trust and host keyboard behavior before rollout.

References:

- [x3270 4.5ga6 source](https://x3270.bgp.nu/download/04.05/suite3270-4.5ga6-src.tgz):
  `x3270/resources.c`, `x3270/keymap.c`, `x3270/save.c`, `Common/unicode.c`.
- [UMS file upload](https://kb.igel.com/en/universal-management-suite/current/upload-and-assign-files-in-the-igel-ums-web-app).
- [UMS file/profile assignment](https://kb.igel.com/en/universal-management-suite/current/files-registering-files-on-the-igel-ums-server-and).
