# Speak each line read from stdin with Windows' built-in voice (System.Speech / SAPI).
param([int]$Rate = 1, [string]$Voice = "")
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = $Rate
if ($Voice) { try { $s.SelectVoice($Voice) } catch {} }
$s.SetOutputToDefaultAudioDevice()
while (($line = [Console]::In.ReadLine()) -ne $null) {
  $t = $line.Trim()
  if ($t) { try { $s.Speak($t) } catch {} }
}
