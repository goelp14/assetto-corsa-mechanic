# ACC shared-memory bridge: streams ACC's physics/graphics/static pages to stdout as framed binary.
# Used when the mechanic runs inside WSL (Linux cannot open Windows named shared memory).
# Frame: "VRE1" + kind (u8) + length (u32 LE) + payload.
#   kind 0 = ACC not running (no payload)
#   kind 1 = physics (800 B) + graphics (1588 B)
#   kind 2 = static (820 B)
param([int]$Hz = 50)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Core
$out = [Console]::OpenStandardOutput()
$magic = [Text.Encoding]::ASCII.GetBytes("VRE1")
$R = [System.IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read
$PHYS = 800; $GFX = 1588; $STAT = 820

function Send([byte]$kind, [byte[]]$payload) {
  $out.Write($magic, 0, 4)
  $out.WriteByte($kind)
  $n = if ($payload) { $payload.Length } else { 0 }
  $out.Write([BitConverter]::GetBytes([uint32]$n), 0, 4)
  if ($n -gt 0) { $out.Write($payload, 0, $n) }
  $out.Flush()
}

function OpenView($name, $size) {
  $m = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting($name, [System.IO.MemoryMappedFiles.MemoryMappedFileRights]::Read)
  return @($m, $m.CreateViewAccessor(0, $size, $R))
}

$period = [Math]::Max(5, [int](1000 / $Hz))
while ($true) {
  try {
    $p = OpenView "Local\acpmf_physics" $PHYS
    $g = OpenView "Local\acpmf_graphics" $GFX
    $s = OpenView "Local\acpmf_static" $STAT
  } catch {
    Send 0 $null
    Start-Sleep -Milliseconds 1000
    continue
  }
  $buf = New-Object byte[] ($PHYS + $GFX)
  $sbuf = New-Object byte[] $STAT
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $lastStatic = -10000
  try {
    while ($true) {
      $t0 = $sw.ElapsedMilliseconds
      if ($t0 - $lastStatic -ge 2000) {
        [void]$s[1].ReadArray(0, $sbuf, 0, $STAT)
        Send 2 $sbuf
        $lastStatic = $t0
      }
      [void]$p[1].ReadArray(0, $buf, 0, $PHYS)
      [void]$g[1].ReadArray(0, $buf, $PHYS, $GFX)
      Send 1 $buf
      $left = $period - ($sw.ElapsedMilliseconds - $t0)
      if ($left -gt 0) { [Threading.Thread]::Sleep([int]$left) }
    }
  } catch [System.IO.IOException] {
    exit 0   # reader went away (pipe closed)
  } finally {
    foreach ($v in @($p, $g, $s)) { try { $v[1].Dispose(); $v[0].Dispose() } catch {} }
  }
}
