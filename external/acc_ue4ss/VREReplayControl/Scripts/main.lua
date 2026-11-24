--[[
  VREReplayControl: lets the VRE replay recorder drive ACC's *own* replay functions.

  ACC (UE 4.26) exposes these as callable UFunctions (found in AC2-Win64-Shipping.exe):
    SetCurrentReplayTimeToSeconds(seconds)  SetCurrentReplayPausedState(paused)
    GetCurrentReplayCurrentTimeInSeconds()  GetCurrentReplayTotalTimeInSeconds()
    GetStartReplayTimeInSeconds()

  IPC is two small files next to this script (no sockets, no input simulation):
    ipc/cmd.txt     written by the recorder: "<id> <verb> [arg]"   verbs: status | pause | play | seek <s>
    ipc/status.txt  written here: key=value lines (in_replay, current_s, total_s, start_s, last_id, result)

  Safety: commands are refused unless a replay is loaded (total replay time > 0). Nothing runs in
  live sessions.
--]]

local DIR = "ue4ss/Mods/VREReplayControl/ipc/"
local CMD = DIR .. "cmd.txt"
local HANDLERS = "ue4ss/Mods/VREReplayControl/Scripts/handlers.lua"
local lastId = -1

-- A command file left from a previous ACC session (e.g. the "quit" that ended a capture run) must never run
-- on the next launch: remember its id as already handled and remove it.
do
    local f = io.open(CMD, "r")
    if f then
        local line = f:read("*l") or ""
        f:close()
        lastId = tonumber(line:match("^(%d+)")) or -1
        os.remove(CMD)
    end
end

local function log(msg) print("[VREReplayControl] " .. tostring(msg) .. "\n") end

local function poll()
    local f = io.open(CMD, "r")
    if not f then return end
    local line = f:read("*l")
    f:close()
    if not line then return end
    local id, verb, arg = line:match("^(%d+)%s+(%S+)%s*(.-)%s*$")
    id = tonumber(id)
    if not id or id == lastId then return end
    lastId = id
    os.remove(CMD)                     -- consume it: a command runs once, never again
    ExecuteInGameThread(function()
        local okL, H = pcall(dofile, HANDLERS)            -- fresh handlers every command
        if not okL or type(H) ~= "table" then
            log("handlers failed to load: " .. tostring(H))
            return
        end
        local ok, st, res = pcall(H.handle, id, verb, arg)
        if not ok then st, res = {}, "error: " .. tostring(st) end
        H.writeStatus(st or {}, id, res)
    end)
end

LoopAsync(50, function()
    local ok, err = pcall(poll)
    if not ok then log("poll error: " .. tostring(err)) end
    return false   -- keep looping
end)

log("loaded")
