-- VREReplayControl command handlers. Re-read from disk on every command (no ACC restart needed).
local M = {}
local DIR = "ue4ss/Mods/VREReplayControl/ipc/"
local CMD, STATUS = DIR .. "cmd.txt", DIR .. "status.txt"
local lastId = -1
local owner = nil          -- object that has the replay UFunctions (resolved once)
local ownerName = ""

local function log(msg) print("[VREReplayControl] " .. tostring(msg) .. "\n") end

local function candidates()
    local out = {}
    local pc = FindFirstOf("PlayerController")
    if pc and pc:IsValid() then
        table.insert(out, pc)
        local ok, cm = pcall(function() return pc.CheatManager end)
        if ok and cm and cm:IsValid() then table.insert(out, cm) end
        local okh, hud = pcall(function() return pc.MyHUD end)
        if okh and hud and hud:IsValid() then table.insert(out, hud) end
    end
    for _, cls in ipairs({ "GameModeBase", "GameStateBase", "GameInstance", "HUD" }) do
        local o = FindFirstOf(cls)
        if o and o:IsValid() then table.insert(out, o) end
    end
    return out
end

local function resolveOwner()
    if owner and owner:IsValid() then return owner end
    owner = nil
    for _, o in ipairs(candidates()) do
        local ok, v = pcall(function() return o:GetCurrentReplayTotalTimeInSeconds() end)
        if ok and type(v) == "number" then
            owner, ownerName = o, o:GetFullName()
            log("replay functions found on " .. ownerName)
            return owner
        end
    end
    return nil
end

local function readStatus()
    local o = resolveOwner()
    if not o then return { in_replay = false, owner = "" } end
    local okT, total = pcall(function() return o:GetCurrentReplayTotalTimeInSeconds() end)
    local okC, cur = pcall(function() return o:GetCurrentReplayCurrentTimeInSeconds() end)
    local okS, start = pcall(function() return o:GetStartReplayTimeInSeconds() end)
    total = okT and total or 0
    return { in_replay = (type(total) == "number" and total > 0), current_s = okC and cur or -1,
             total_s = total, start_s = okS and start or -1, owner = ownerName }
end

function M.writeStatus(st, id, result)
    local f = io.open(STATUS .. ".tmp", "w")
    if not f then return end
    f:write(string.format("in_replay=%s\ncurrent_s=%.4f\ntotal_s=%.4f\nstart_s=%.4f\nlast_id=%d\nresult=%s\nowner=%s\nclock=%.3f\n",
        tostring(st.in_replay), st.current_s or -1, st.total_s or 0, st.start_s or -1, id, result or "",
        st.owner or "", os.clock()))
    f:close()
    os.remove(STATUS)
    os.rename(STATUS .. ".tmp", STATUS)
end

-- one-off introspection: where a UFunction lives and what it takes (written to ipc/find.txt)
local function describe(name)
    local lines = {}
    ForEachUObject(function(obj)
        local ok, cls = pcall(function() return obj:GetClass():GetFName():ToString() end)
        if ok and (cls == "Function" or cls == "ScriptStruct") then
            local okn, n = pcall(function() return obj:GetFName():ToString() end)
            if okn and n == name then
                local params = {}
                pcall(function()
                    obj:ForEachProperty(function(prop)
                        local extra = ""
                        pcall(function() extra = "<" .. prop:GetStruct():GetFName():ToString() .. ">" end)
                        pcall(function() extra = "<" .. prop:GetEnum():GetFName():ToString() .. ">" end)
                        table.insert(params, prop:GetFName():ToString() .. ":" .. prop:GetClass():GetFName():ToString() .. extra)
                    end)
                end)
                table.insert(lines, obj:GetFullName() .. " | " .. table.concat(params, ", "))
            end
        end
    end)
    local f = io.open(DIR .. "find.txt", "w")
    if f then f:write(table.concat(lines, "\n") .. "\n"); f:close() end
    return #lines
end

-- ACC's saved-replay list, exactly as its replay menu sees it
local function replayList()
    local lib = StaticFindObject("/Script/AC2.Default__ReplayBlueprintFunctionLibrary")
    if not lib or not lib:IsValid() then error("ReplayBlueprintFunctionLibrary not found") end
    local out = {}
    lib:GetReplayList(out, 0)                 -- replayStore 0 = Saved; out-params land in the table
    local arr = out.replayInfos or out[1]
    if not arr then
        local keys = {}
        for k, v in pairs(out) do table.insert(keys, tostring(k) .. "=" .. type(v)) end
        error("GetReplayList out-params: " .. table.concat(keys, ","))
    end
    local okG, inner = pcall(function() return arr:get() end)   -- out-params arrive wrapped (LocalUnrealParam)
    if okG and inner ~= nil then arr = inner end
    local infos = {}
    if type(arr) == "table" then
        for _, v in ipairs(arr) do table.insert(infos, v) end
        return infos
    end
    local okF = pcall(function()
        arr:ForEach(function(_, elem) table.insert(infos, elem:get()) end)
    end)
    if okF then return infos end
    -- other shapes UE4SS may hand back
    local tries = {}
    local okN, n = pcall(function() return arr:GetArrayNum() end)
    table.insert(tries, "GetArrayNum=" .. tostring(okN and n or "x"))
    if okN and n and n > 0 then
        for i = 1, n do
            local okE, e = pcall(function() return arr[i] end)
            if okE and e then
                local okg, ev = pcall(function() return e:get() end)
                table.insert(infos, okg and ev or e)
            end
        end
        if #infos > 0 then return infos end
    end
    local okS, sz = pcall(function() return #arr end)
    table.insert(tries, "len=" .. tostring(okS and sz or "x"))
    local okT, ts = pcall(function() return tostring(arr) end)
    table.insert(tries, "str=" .. tostring(okT and ts or "x"))
    local okF2 = pcall(function() arr:ForEach(function(_, elem) table.insert(infos, elem:get()) end) end)
    table.insert(tries, "ForEach=" .. tostring(okF2))
    if okF2 and #infos > 0 then return infos end
    -- describe what we got
    log("replayList tries: " .. table.concat(tries, " "))
    local mt = getmetatable(arr)
    local names = {}
    if mt then for k in pairs(mt) do table.insert(names, tostring(k)) end end
    local okt, tn = pcall(function() return arr:type() end)
    error("replayInfos is " .. type(arr) .. " " .. tostring(okt and tn or "") .. " methods: " .. table.concat(names, ","))
end

local function fieldStr(info, key)
    local ok, v = pcall(function() return info[key] end)
    if not ok or v == nil then return "" end
    local ok2, s = pcall(function() return v:ToString() end)
    if ok2 then return s end
    return tostring(v)
end

local function listReplays()
    local infos = replayList()
    local lines = {}
    for _, info in ipairs(infos) do
        table.insert(lines, table.concat({ fieldStr(info, "replayName"), fieldStr(info, "serverName"),
            fieldStr(info, "trackId"), fieldStr(info, "carModelTypeId"), fieldStr(info, "creationDate") }, " | "))
    end
    local f = io.open(DIR .. "replays.txt", "w")
    if f then f:write(table.concat(lines, "\n") .. "\n"); f:close() end
    return #lines
end

-- load "Filename=...;TrackId=2;Length=2441.6;carModelTypeId=32;Version=25" through the menu's own LoadReplay
local function loadReplay(arg)
    local gm = FindFirstOf("AcMenuGameMode")
    if not gm or not gm:IsValid() then return "refused: not in ACC's main menu" end
    local info = { Filename = "", Version = 25, TrackId = 0, Length = 0.0, carModelTypeId = 0,
                   store = 0, Type = 0, Category = 0, ServerName = "" }
    for k, v in string.gmatch(arg, "([%w_]+)=([^;]*)") do
        if k == "Filename" or k == "ServerName" then info[k] = v else info[k] = tonumber(v) or 0 end
    end
    if info.Filename == "" then return "error: Filename missing" end
    local ok, res = pcall(function() return gm:LoadReplay(info, 0, nil) end)
    if not ok then return "error: " .. tostring(res) end
    return "ok: LoadReplay returned " .. tostring(res)
end

-- leave the replay and go back to ACC's main menu (only from a replay)
local function toMenu()
    local gm = FindFirstOf("AcRaceGameMode")
    if not gm or not gm:IsValid() then return "ok: already in the menu" end
    local st = readStatus()
    if not st.in_replay then return "refused: not in a replay (won't close a live session)" end
    -- ACC's menu lives in the map /Game/Maps/NewUI (its log shows "Browse: /Game/Maps/NewUI"); open it
    local statics = StaticFindObject("/Script/Engine.Default__GameplayStatics")
    if not statics or not statics:IsValid() then return "error: GameplayStatics not found" end
    local ok, err = pcall(function() statics:OpenLevel(gm, FName("/Game/Maps/NewUI"), true, "Name=Player") end)
    return ok and "ok" or ("error: " .. tostring(err))
end

local function where()
    local menu = FindFirstOf("AcMenuGameMode")
    if menu and menu:IsValid() then return "menu" end
    local race = FindFirstOf("AcRaceGameMode")
    if race and race:IsValid() then return "race" end
    return "loading"
end

local function quitGame()
    local race = FindFirstOf("AcRaceGameMode")
    if race and race:IsValid() and not readStatus().in_replay then
        return "refused: a live session is running"
    end
    local ks = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
    local pc = FindFirstOf("PlayerController")
    if not ks or not ks:IsValid() or not pc or not pc:IsValid() then return "error: cannot quit" end
    local ok, err = pcall(function() ks:QuitGame(pc, pc, 0, false) end)
    return ok and "ok" or ("error: " .. tostring(err))
end

function M.handle(id, verb, arg)
    if verb == "speed" then
        local st = readStatus()
        if not st.in_replay then return st, "refused: no replay loaded" end
        local x = tonumber(arg) or 1.0
        local ok, err = pcall(function() resolveOwner():SetTimeMultiplier(x) end)
        return readStatus(), ok and "ok" or ("error: " .. tostring(err))
    end
    if verb == "quit" then
        local ok, r = pcall(quitGame)
        return readStatus(), ok and r or ("error: " .. tostring(r))
    end
    if verb == "menu" then
        local ok, r = pcall(toMenu)
        return readStatus(), ok and r or ("error: " .. tostring(r))
    end
    if verb == "where" then
        local ok, r = pcall(where)
        return readStatus(), ok and r or "loading"
    end
    if verb == "replays" then
        local ok, n = pcall(listReplays)
        return readStatus(), ok and ("listed " .. tostring(n)) or ("error: " .. tostring(n))
    end
    if verb == "load" then
        local ok, r = pcall(loadReplay, arg)
        return readStatus(), ok and r or ("error: " .. tostring(r))
    end
    if verb == "find" then
        local ok, n = pcall(describe, arg)
        return readStatus(), ok and ("found " .. tostring(n)) or ("error: " .. tostring(n))
    end
    local st = readStatus()
    if verb == "status" then return st, "ok" end
    if not st.in_replay then return st, "refused: no replay loaded" end
    local o = resolveOwner()
    local ok, err
    if verb == "pause" then
        ok, err = pcall(function() o:SetCurrentReplayPausedState(true) end)
    elseif verb == "play" then
        ok, err = pcall(function() o:SetCurrentReplayPausedState(false) end)
    elseif verb == "seek" then
        local t = tonumber(arg)
        if not t then return st, "error: seek needs seconds" end
        t = math.floor(t)      -- ACC's SetCurrentReplayTimeToSeconds takes whole seconds (a float lands at 0)
        ok, err = pcall(function() o:SetCurrentReplayTimeToSeconds(t) end)
    else
        return st, "error: unknown verb " .. tostring(verb)
    end
    return readStatus(), ok and "ok" or ("error: " .. tostring(err))
end


return M
