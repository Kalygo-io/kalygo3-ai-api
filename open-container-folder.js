const { exec } = require("child_process");

const printColor = (...args) => console.log("\x1b[36m%s\x1b[0m", ...args);

const workingDirectory = process.cwd().replace(/\\/g, "/");

const hostWorkspaceFileHex = Buffer.from(`${workingDirectory}`).toString("hex");

const containerWorkspaceFile = "/code";

const command = `cursor --folder-uri "cursor://dev-container+${hostWorkspaceFileHex}${containerWorkspaceFile}"`;

printColor(command);
exec(command);
