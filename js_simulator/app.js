const { app, BrowserWindow } = require('electron');
const { fork } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow;
let serverProcess;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        backgroundColor: '#1e1e1e',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    // Hide menu bar
    mainWindow.setMenuBarVisibility(false);

    // Wait for server to be ready
    const pollServer = () => {
        http.get('http://localhost:3000', (res) => {
            if (res.statusCode === 200) {
                mainWindow.loadURL('http://localhost:3000');
            } else {
                setTimeout(pollServer, 500);
            }
        }).on('error', () => {
            setTimeout(pollServer, 500);
        });
    };
    pollServer();

    mainWindow.on('closed', function () {
        mainWindow = null;
    });
}

function startServer() {
    // Spawn server.js as a separate process to use system Node (avoiding Electron native rebuilds)
    serverProcess = fork(path.join(__dirname, 'server.js'), [], {
        silent: false
        // stdio: 'inherit' to see logs in console if run from CLI
    });

    serverProcess.on('exit', (code) => {
        console.log(`Server process exited with code ${code}`);
    });
}

app.on('ready', () => {
    startServer();
    createWindow();
});

app.on('window-all-closed', function () {
    if (serverProcess) {
        serverProcess.kill();
    }
    app.quit();
});

app.on('quit', () => {
    if (serverProcess) {
        serverProcess.kill();
    }
});
