const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

let mainWindow;
const settingsPath = path.join(app.getPath('userData'), 'dsp-settings.json');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: -100, y: -100 },
    backgroundColor: '#131327',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, 'icon.png'),
  });

  mainWindow.loadFile('index.html');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Window control IPC handlers
ipcMain.on('window-minimize', () => {
  mainWindow?.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});

ipcMain.on('window-close', () => {
  mainWindow?.close();
});

ipcMain.on('window-fullscreen', () => {
  mainWindow?.setFullScreen(!mainWindow.isFullScreen());
});

// Save file dialog
ipcMain.handle('dialog:open-save-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select DSP Save File (.dsv)',
    filters: [{ name: 'DSP Save Files', extensions: ['dsv'] }],
    properties: ['openFile'],
  });
  return result.canceled ? null : result.filePaths[0];
});

// Save file analysis via Python bridge
ipcMain.handle('save:analyze', async (event, filePath) => {
  return new Promise((resolve, reject) => {
    if (!filePath || !fs.existsSync(filePath)) {
      resolve({ error: 'File not found: ' + filePath });
      return;
    }

    const pythonScript = path.join(__dirname, 'save_analyzer.py');
    if (!fs.existsSync(pythonScript)) {
      resolve({ error: 'save_analyzer.py not found. Please ensure it exists in the app directory.' });
      return;
    }

    // Try python3 first, then python
    const tryPython = (cmd) => {
      execFile(cmd, [pythonScript, filePath], {
        maxBuffer: 50 * 1024 * 1024,
        timeout: 120000,
        cwd: __dirname,
      }, (error, stdout, stderr) => {
        if (error) {
          if (cmd === 'python3') {
            tryPython('python');
            return;
          }
          resolve({
            error: 'Python execution failed',
            detail: error.message,
            stderr: stderr?.substring(0, 500),
          });
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch (e) {
          resolve({ error: 'Invalid JSON from analyzer', raw: stdout?.substring(0, 1000) });
        }
      });
    };

    tryPython('python3');
  });
});

// Settings persistence
ipcMain.handle('settings:get', async () => {
  try {
    if (fs.existsSync(settingsPath)) {
      return JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    }
  } catch (e) { /* ignore */ }
  return {};
});

ipcMain.handle('settings:set', async (event, data) => {
  try {
    fs.writeFileSync(settingsPath, JSON.stringify(data, null, 2));
    return { success: true };
  } catch (e) {
    return { error: e.message };
  }
});
