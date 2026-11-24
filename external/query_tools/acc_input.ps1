# Drive ACC's window: focus, screenshot (works while covered), mouse moves/clicks, key presses.
# Reads one command per line from stdin and answers one line per command:
#   focus                 -> bring ACC to the front (remembers the previous foreground window)
#   restore               -> give focus back to the previous window
#   shot <path>           -> PNG of ACC's client area (PrintWindow; works in the background)
#   move <x> <y>          -> move the mouse to ACC client pixel (x, y)
#   click <x> <y>         -> left click at ACC client pixel (x, y)
#   key <vk> [hold_ms]    -> press a virtual-key code (e.g. 0x70 = F1, 0x20 = space)
#   size                  -> client width/height
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class AccIn {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx, dy; public uint data, flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort vk, scan; public uint flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Explicit)] public struct UNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public UNION u; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern uint SendInput(uint n, INPUT[] i, int size);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  public static void Mouse(uint flags) { var i = new INPUT[1]; i[0].type = 0; i[0].u.mi.flags = flags; SendInput(1, i, Marshal.SizeOf(typeof(INPUT))); }
  public static void MoveAbs(int x, int y, int sw, int sh) { var i = new INPUT[1]; i[0].type = 0; i[0].u.mi.dx = (int)(x * 65535.0 / (sw - 1)); i[0].u.mi.dy = (int)(y * 65535.0 / (sh - 1)); i[0].u.mi.flags = 0x0001 | 0x8000; SendInput(1, i, Marshal.SizeOf(typeof(INPUT))); }
  public static void MoveRel(int dx, int dy) { var i = new INPUT[1]; i[0].type = 0; i[0].u.mi.dx = dx; i[0].u.mi.dy = dy; i[0].u.mi.flags = 0x0001; SendInput(1, i, Marshal.SizeOf(typeof(INPUT))); }
  public static void Key(ushort vk, bool up) {
    var i = new INPUT[1]; i[0].type = 1; i[0].u.ki.vk = vk; i[0].u.ki.scan = (ushort)MapVirtualKey(vk, 0);
    i[0].u.ki.flags = 0x0008u | (up ? 0x0002u : 0u);   // KEYEVENTF_SCANCODE (games read scan codes) | KEYUP
    SendInput(1, i, Marshal.SizeOf(typeof(INPUT)));
  }
}
"@
[void][AccIn]::SetProcessDPIAware()
$prev = [IntPtr]::Zero
function Hwnd { $p = Get-Process AC2-Win64-Shipping -ErrorAction SilentlyContinue | Select-Object -First 1; if (-not $p) { return [IntPtr]::Zero }; return $p.MainWindowHandle }
function ToScreen($h, $x, $y) { $pt = New-Object AccIn+POINT; $pt.X = [int]$x; $pt.Y = [int]$y; [void][AccIn]::ClientToScreen($h, [ref]$pt); return $pt }

while (($line = [Console]::In.ReadLine()) -ne $null) {
  $a = $line.Trim() -split '\s+', 3
  $h = Hwnd
  try {
    if ($h -eq [IntPtr]::Zero) { "ERR acc not running"; continue }
    switch ($a[0]) {
      "focus" {
        $script:prev = [AccIn]::GetForegroundWindow()
        if ([AccIn]::IsIconic($h)) { [void][AccIn]::ShowWindow($h, 9) }
        [AccIn]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [AccIn]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)   # ALT tap lets us take focus
        $ok = [AccIn]::SetForegroundWindow($h); Start-Sleep -Milliseconds 300
        "OK $ok $([AccIn]::GetForegroundWindow() -eq $h)"
      }
      "restore" { if ($script:prev -ne [IntPtr]::Zero) { [AccIn]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [AccIn]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero); [void][AccIn]::SetForegroundWindow($script:prev) }; "OK" }
      "size" { $r = New-Object AccIn+RECT; [void][AccIn]::GetClientRect($h, [ref]$r); "OK $($r.R) $($r.B)" }
      "shot" {
        $r = New-Object AccIn+RECT; [void][AccIn]::GetClientRect($h, [ref]$r)
        $bmp = New-Object Drawing.Bitmap ($r.R), ($r.B); $g = [Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
        $ok = [AccIn]::PrintWindow($h, $dc, 2); $g.ReleaseHdc($dc); $bmp.Save($a[1], [Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
        "OK $ok"
      }
      "move" {
        $pt = ToScreen $h $a[1] $a[2]
        $sb = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        for ($k = 6; $k -ge 0; $k--) { [AccIn]::MoveAbs($pt.X - 4 * $k, $pt.Y - 3 * $k, $sb.Width, $sb.Height); Start-Sleep -Milliseconds 10 }
        "OK"
      }
      "click" {
        $pt = ToScreen $h $a[1] $a[2]; [void][AccIn]::SetCursorPos($pt.X - 4, $pt.Y - 4)
        for ($k = 0; $k -lt 4; $k++) { [AccIn]::MoveRel(1, 1); Start-Sleep -Milliseconds 8 }
        Start-Sleep -Milliseconds 80
        [AccIn]::Mouse(0x0002); Start-Sleep -Milliseconds 50; [AccIn]::Mouse(0x0004); "OK"
      }
      "key" {
        $vk = [Convert]::ToUInt16($a[1], 16); $hold = if ($a.Count -gt 2) { [int]$a[2] } else { 60 }
        [AccIn]::Key($vk, $false); Start-Sleep -Milliseconds $hold; [AccIn]::Key($vk, $true); "OK"
      }
      "chord" {
        # chord <mod_vk[+mod_vk...]> <vk> : e.g. chord 11+10 78 = Ctrl+Shift+F9
        $mods = @($a[1] -split '\+' | ForEach-Object { [Convert]::ToUInt16($_, 16) }); $vk = [Convert]::ToUInt16(($a[2] -split '\s+')[0], 16)
        foreach ($m in $mods) { [AccIn]::Key($m, $false); Start-Sleep -Milliseconds 30 }
        [AccIn]::Key($vk, $false); Start-Sleep -Milliseconds 80; [AccIn]::Key($vk, $true); Start-Sleep -Milliseconds 30
        [array]::Reverse($mods); foreach ($m in $mods) { [AccIn]::Key($m, $true); Start-Sleep -Milliseconds 20 }
        "OK"
      }
      "fg" { "OK $([AccIn]::GetForegroundWindow().ToInt64())" }
      "activate" {
        $hw = [IntPtr][long]$a[1]
        [AccIn]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [AccIn]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
        if ([AccIn]::IsIconic($hw)) { [void][AccIn]::ShowWindow($hw, 9) }
        "OK $([AccIn]::SetForegroundWindow($hw))"
      }
      default { "ERR unknown command $($a[0])" }
    }
  } catch { "ERR $($_.Exception.Message)" }
}
