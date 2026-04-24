import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const MYPY_INI_FILENAME = '.mypy.ini';
const MYPY_CONFIG_SECTION_HEADER = '[mypy]';


function normalizeClaudeHooksPathToForwardSlashes(claudeHooksDirectory) {
    return claudeHooksDirectory.replace(/\\/g, '/');
}


function buildExpectedMypyPathLine(claudeHooksDirectory) {
    const claudeHooksAsForwardSlashes = normalizeClaudeHooksPathToForwardSlashes(claudeHooksDirectory);
    return `mypy_path = ${claudeHooksAsForwardSlashes}`;
}


function buildMypyIniContentForClaudeHooks(claudeHooksDirectory) {
    const expectedMypyPathLine = buildExpectedMypyPathLine(claudeHooksDirectory);
    return `${MYPY_CONFIG_SECTION_HEADER}\n${expectedMypyPathLine}\n`;
}


export function installMypyIniForClaudeHooks({ homeDirectory, claudeHooksDirectory }) {
    const mypyIniDestinationPath = join(homeDirectory, MYPY_INI_FILENAME);
    const expectedMypyPathLine = buildExpectedMypyPathLine(claudeHooksDirectory);

    if (existsSync(mypyIniDestinationPath)) {
        const existingMypyIniContent = readFileSync(mypyIniDestinationPath, 'utf8');
        if (existingMypyIniContent.includes(expectedMypyPathLine)) {
            return { action: 'already-configured', path: mypyIniDestinationPath };
        }
        return {
            action: 'skipped-existing',
            path: mypyIniDestinationPath,
            expectedLine: expectedMypyPathLine,
        };
    }

    const mypyIniContent = buildMypyIniContentForClaudeHooks(claudeHooksDirectory);
    writeFileSync(mypyIniDestinationPath, mypyIniContent);
    return { action: 'created', path: mypyIniDestinationPath };
}
