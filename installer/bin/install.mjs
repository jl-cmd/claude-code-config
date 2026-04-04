#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const claudeHome = path.join(os.homedir(), '.claude');
const installDirectory = path.join(claudeHome, 'agent-gate');
const repositoryUrl = 'https://github.com/jl-cmd/agent-gate.git';
const settingsPath = path.join(claudeHome, 'settings.json');
const venvDirectoryName = '.venv';
const hookTimeoutMs = 10000;
const hookScripts = {
    enforcer: 'gate_enforcer.py',
    trigger: 'gate_trigger.py',
    cleanup: 'session_cleanup.py'
};
const logPrefix = {
    info: '+',
    skip: '~',
    error: '!'
};
const cliFlags = {
    verbose: '--verbose',
    nonInteractive: '--non-interactive',
    uninstall: '--uninstall',
    update: '--update',
    help: '--help'
};
const hookMatcherByEvent = { PreToolUse: 'Read|Write|Edit|Bash|Glob|Grep|Agent|Task', UserPromptSubmit: '', SessionStart: null };
const eventScriptPairs = [['PreToolUse', hookScripts.enforcer], ['UserPromptSubmit', hookScripts.trigger], ['SessionStart', hookScripts.cleanup]];
function logInfo(message) {
    console.log(`${logPrefix.info} ${message}`);
}
function logSkip(message) {
    console.log(`${logPrefix.skip} ${message}`);
}
function logError(message) {
    console.error(`${logPrefix.error} ${message}`);
}
function parseArguments(argumentValues) {
    const argumentSet = new Set(argumentValues);
    return { shouldShowHelp: argumentSet.has(cliFlags.help), isVerbose: argumentSet.has(cliFlags.verbose), isNonInteractive: argumentSet.has(cliFlags.nonInteractive), shouldUninstall: argumentSet.has(cliFlags.uninstall), shouldUpdate: argumentSet.has(cliFlags.update) };
}
function ensureDirectory(directoryPath) {
    fs.mkdirSync(directoryPath, { recursive: true });
}
function runCommand(commandText, errorContext, isVerbose, workingDirectoryPath) {
    try {
        const commandOutput = execSync(commandText, { encoding: 'utf8', stdio: isVerbose ? 'inherit' : 'pipe', cwd: workingDirectoryPath });
        return typeof commandOutput === 'string' ? commandOutput.trim() : '';
    } catch (executionError) {
        const detail = executionError?.message ? `: ${executionError.message}` : '';
        throw new Error(`${errorContext}${detail}`);
    }
}
function parseVersionParts(versionOutput) {
    const matchedVersion = versionOutput.match(/Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i);
    if (!matchedVersion) return null;
    return { major: Number(matchedVersion[1]), minor: Number(matchedVersion[2]), patch: Number(matchedVersion[3] ?? '0'), text: `${matchedVersion[1]}.${matchedVersion[2]}.${matchedVersion[3] ?? '0'}` };
}
function isSupportedPythonVersion(versionOutput) {
    const versionParts = parseVersionParts(versionOutput);
    if (!versionParts) return false;
    if (versionParts.major > 3) return true;
    return versionParts.major === 3 && versionParts.minor >= 12;
}
function detectPython() {
    const pythonCandidates = [{ command: 'python3', versionCommand: 'python3 --version' }, { command: 'python', versionCommand: 'python --version' }, { command: 'py -3', versionCommand: 'py -3 --version' }];
    for (const eachCandidate of pythonCandidates) {
        try {
            const versionOutput = execSync(eachCandidate.versionCommand, { encoding: 'utf8', stdio: 'pipe' }).trim();
            if (isSupportedPythonVersion(versionOutput)) {
                const parsedVersion = parseVersionParts(versionOutput);
                return {
                    command: eachCandidate.command,
                    version: parsedVersion ? parsedVersion.text : versionOutput
                };
            }
        } catch (error) {
            continue;
        }
    }
    logError('Python 3.12+ not found. Install Python 3.12+ and retry.');
    process.exit(1);
}
function getVenvPython(venvDirectoryPath) {
    if (process.platform === 'win32') {
        return path.join(venvDirectoryPath, 'Scripts', 'python.exe');
    }
    return path.join(venvDirectoryPath, 'bin', 'python');
}
function promptForToken() {
    return new Promise((resolve) => {
        process.stdout.write('Enter GH_TOKEN: ');
        process.stdin.resume();
        process.stdin.setEncoding('utf8');
        process.stdin.once('data', (tokenInput) => {
            process.stdin.pause();
            resolve(tokenInput.trim());
        });
    });
}
function getGitCloneUrl(tokenValue) {
    return repositoryUrl.replace('https://', `https://${tokenValue}@`);
}
function readSettingsOrExit(settingsFilePath) {
    if (!fs.existsSync(settingsFilePath)) {
        return {};
    }
    try {
        const settingsContent = fs.readFileSync(settingsFilePath, 'utf8');
        if (!settingsContent.trim()) {
            return {};
        }
        return JSON.parse(settingsContent);
    } catch (parseError) {
        logError(`Malformed settings.json at ${settingsFilePath}. Fix JSON and retry.`);
        process.exit(1);
    }
}
function writeSettings(settingsFilePath, settingsObject) {
    ensureDirectory(path.dirname(settingsFilePath));
    fs.writeFileSync(settingsFilePath, JSON.stringify(settingsObject, null, 4));
}
function upsertSingleHook(eventHooks, targetHook) {
    const existingIndex = eventHooks.findIndex((eachHook) => {
        const hookCommand = typeof eachHook?.command === 'string' ? eachHook.command : '';
        return hookCommand.includes(targetHook.scriptName);
    });
    const hookPayload = {
        command: targetHook.command,
        timeout: targetHook.timeout
    };
    if (Object.prototype.hasOwnProperty.call(targetHook, 'matcher')) {
        hookPayload.matcher = targetHook.matcher;
    }
    if (existingIndex >= 0) {
        eventHooks[existingIndex] = hookPayload;
        return 'updated';
    }
    eventHooks.push(hookPayload);
    return 'added';
}
function mergeHooks(settingsObject, venvPythonPath, installDirectoryPath) {
    if (!settingsObject.hooks || typeof settingsObject.hooks !== 'object' || Array.isArray(settingsObject.hooks)) settingsObject.hooks = {};
    let addedCount = 0;
    let updatedCount = 0;
    for (const [eventName, scriptName] of eventScriptPairs) {
        if (!Array.isArray(settingsObject.hooks[eventName])) {
            settingsObject.hooks[eventName] = [];
        }
        const hookPath = path.join(installDirectoryPath, 'hooks', scriptName);
        const hookDefinition = {
            scriptName,
            timeout: hookTimeoutMs,
            command: `"${venvPythonPath}" "${hookPath}"`
        };
        const matcherValue = hookMatcherByEvent[eventName];
        if (matcherValue !== null) {
            hookDefinition.matcher = matcherValue;
        }
        const changeType = upsertSingleHook(settingsObject.hooks[eventName], hookDefinition);
        if (changeType === 'updated') {
            updatedCount += 1;
        } else {
            addedCount += 1;
        }
    }
    return { addedCount, updatedCount };
}
function registerAgentGateMcpServer(settingsObject, venvPythonPath, installDirectoryPath) {
    if (!settingsObject.mcpServers || typeof settingsObject.mcpServers !== 'object' || Array.isArray(settingsObject.mcpServers)) {
        settingsObject.mcpServers = {};
    }
    settingsObject.mcpServers['agent-gate'] = {
        type: 'stdio',
        command: venvPythonPath,
        args: [path.join(installDirectoryPath, 'src', 'agent_gate', 'server.py')]
    };
}
function removeAgentGateHooks(settingsObject) {
    if (!settingsObject.hooks || typeof settingsObject.hooks !== 'object') {
        return 0;
    }
    const scriptNames = Object.values(hookScripts);
    let removedCount = 0;
    for (const eachEventName of Object.keys(settingsObject.hooks)) {
        const eventHooks = Array.isArray(settingsObject.hooks[eachEventName]) ? settingsObject.hooks[eachEventName] : [];
        const filteredHooks = eventHooks.filter((eachHook) => {
            const hookCommand = typeof eachHook?.command === 'string' ? eachHook.command : '';
            const shouldRemove = scriptNames.some((scriptName) => hookCommand.includes(scriptName));
            if (shouldRemove) {
                removedCount += 1;
            }
            return !shouldRemove;
        });
        settingsObject.hooks[eachEventName] = filteredHooks;
    }
    return removedCount;
}
function removeAgentGateMcpServer(settingsObject) {
    if (!settingsObject.mcpServers || typeof settingsObject.mcpServers !== 'object') {
        return false;
    }
    if (!Object.prototype.hasOwnProperty.call(settingsObject.mcpServers, 'agent-gate')) {
        return false;
    }
    delete settingsObject.mcpServers['agent-gate'];
    return true;
}
function cloneOrPullRepo(tokenValue, isVerbose) {
    const gitDirectoryPath = path.join(installDirectory, '.git');
    if (fs.existsSync(installDirectory) && fs.existsSync(gitDirectoryPath)) {
        logSkip('agent-gate already cloned, pulling latest...');
        runCommand('git pull', 'git pull failed', isVerbose, installDirectory);
        return;
    }
    ensureDirectory(path.dirname(installDirectory));
    const cloneUrl = getGitCloneUrl(tokenValue);
    runCommand(`git clone ${cloneUrl} "${installDirectory}"`, 'git clone failed. Check GH_TOKEN and repo access', isVerbose);
    logInfo('Cloned agent-gate to ~/.claude/agent-gate/');
}
function createVenvIfNeeded(pythonCommand, venvDirectoryPath, isVerbose) {
    if (fs.existsSync(venvDirectoryPath)) {
        logSkip('venv already exists');
        return false;
    }
    runCommand(`${pythonCommand} -m venv "${venvDirectoryPath}"`, 'venv creation failed', isVerbose);
    logInfo('Created Python venv');
    return true;
}
function installPackages(venvPythonPath, isVerbose) {
    const packageCorePath = path.join(installDirectory, 'packages', 'agent-gate-core');
    const packageClaudePath = path.join(installDirectory, 'packages', 'agent-gate-claude');
    const packagePromptPath = path.join(installDirectory, 'packages', 'agent-gate-prompt-refinement');
    const editableInstallCommand = [
        `"${venvPythonPath}" -m pip install`,
        `-e "${packageCorePath}"`,
        `-e "${packageClaudePath}"`,
        `-e "${packagePromptPath}"`,
        `-e "${installDirectory}[dev]"`
    ].join(' ');
    runCommand(editableInstallCommand, 'pip install failed. Confirm Python >= 3.12', isVerbose);
    logInfo('Installed agent-gate packages');
}
function verifyInstall(venvPythonPath, isVerbose) {
    try {
        runCommand(`"${venvPythonPath}" -c "from agent_gate.server import create_mcp; print('OK')"`, 'verification failed', isVerbose);
        logInfo('Verification passed');
        return true;
    } catch (verificationError) {
        logSkip('Verification warning: import check failed, install remains usable');
        return false;
    }
}
function printSummary(pythonCommand, pythonVersion, venvDirectoryPath, hookResult) {
    const hooksDisplayText = hookResult.updatedCount === 3 ? 'Updated 3 existing hooks' : 'Merged 3 hooks';
    if (hookResult.updatedCount === 3) logSkip(hooksDisplayText);
    else logInfo(hooksDisplayText);
    console.log('');
    console.log('agent-gate installed successfully');
    console.log('');
    console.log('  Location:  ~/.claude/agent-gate/');
    console.log(`  Python:    ${pythonCommand} ${pythonVersion}`);
    console.log(`  Venv:      ${venvDirectoryPath}`);
    console.log(`  Hooks:     ${hooksDisplayText}`);
    console.log('  MCP:       agent-gate registered');
    console.log('');
    console.log('Restart Claude Code to activate.');
}
async function runInstallFlow(flags) {
    let tokenValue = process.env.GH_TOKEN?.trim() ?? '';
    if (!tokenValue) {
        if (flags.isNonInteractive) {
            logError('GH_TOKEN is required in non-interactive mode');
            process.exit(1);
        }
        tokenValue = await promptForToken();
    }
    if (!tokenValue) {
        logError('GH_TOKEN is required');
        process.exit(1);
    }
    const pythonDetection = detectPython();
    cloneOrPullRepo(tokenValue, flags.isVerbose);
    const venvDirectoryPath = path.join(installDirectory, venvDirectoryName);
    createVenvIfNeeded(pythonDetection.command, venvDirectoryPath, flags.isVerbose);
    const venvPythonPath = getVenvPython(venvDirectoryPath);
    installPackages(venvPythonPath, flags.isVerbose);
    const settingsObject = readSettingsOrExit(settingsPath);
    const hookResult = mergeHooks(settingsObject, venvPythonPath, installDirectory);
    registerAgentGateMcpServer(settingsObject, venvPythonPath, installDirectory);
    writeSettings(settingsPath, settingsObject);
    logInfo('Registered agent-gate MCP server');
    verifyInstall(venvPythonPath, flags.isVerbose);
    printSummary(pythonDetection.command, pythonDetection.version, venvDirectoryPath, hookResult);
}
function runUpdateFlow(flags) {
    if (!fs.existsSync(path.join(installDirectory, '.git'))) {
        logError('agent-gate is not installed. Run install first.');
        process.exit(1);
    }
    const venvDirectoryPath = path.join(installDirectory, venvDirectoryName);
    const venvPythonPath = getVenvPython(venvDirectoryPath);
    runCommand('git pull', 'git pull failed during update', flags.isVerbose, installDirectory);
    installPackages(venvPythonPath, flags.isVerbose);
    console.log('agent-gate updated. Restart Claude Code.');
}
async function runUninstallFlow(flags) {
    if (!flags.isNonInteractive) {
        const answer = await new Promise((resolve) => {
            process.stdout.write('Remove ~/.claude/agent-gate? [y/N]: ');
            process.stdin.resume();
            process.stdin.setEncoding('utf8');
            process.stdin.once('data', (input) => {
                process.stdin.pause();
                resolve(input.trim().toLowerCase());
            });
        });
        if (answer !== 'y' && answer !== 'yes') {
            logSkip('Uninstall cancelled');
            return;
        }
    }
    if (fs.existsSync(installDirectory)) {
        fs.rmSync(installDirectory, { recursive: true, force: true });
        logInfo('Removed ~/.claude/agent-gate/');
    } else {
        logSkip('Install directory not found');
    }
    const settingsObject = readSettingsOrExit(settingsPath);
    const removedHooks = removeAgentGateHooks(settingsObject);
    if (removedHooks > 0) {
        logInfo(`Removed ${removedHooks} gate hooks from settings.json`);
    } else {
        logSkip('No gate hooks found in settings.json');
    }
    const mcpRemoved = removeAgentGateMcpServer(settingsObject);
    if (mcpRemoved) {
        logInfo('Removed agent-gate MCP server');
    } else {
        logSkip('agent-gate MCP server not found');
    }
    writeSettings(settingsPath, settingsObject);
    console.log('agent-gate uninstalled. Restart Claude Code.');
}
function printHelp() {
    console.log('Usage: agent-gate-installer [--verbose] [--non-interactive] [--update] [--uninstall] [--help]');
    console.log('');
    console.log('Options:');
    console.log('  --verbose          Show child process output');
    console.log('  --non-interactive  Fail instead of prompting for GH_TOKEN');
    console.log('  --update           Pull latest repo and reinstall packages');
    console.log('  --uninstall        Remove agent-gate install and settings entries');
    console.log('  --help             Show this help text');
}
async function main() {
    void fileURLToPath(import.meta.url);
    ensureDirectory(claudeHome);
    const flags = parseArguments(process.argv.slice(2));
    if (flags.shouldShowHelp) {
        printHelp();
        return;
    }
    if (flags.shouldUninstall) {
        await runUninstallFlow(flags);
        return;
    }
    if (flags.shouldUpdate) {
        runUpdateFlow(flags);
        return;
    }
    await runInstallFlow(flags);
}
main().catch((error) => {
    logError(error.message);
    process.exit(1);
});
