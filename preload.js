const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  fullscreen: () => ipcRenderer.send('window-fullscreen'),
  // Save file operations
  openSaveFile: () => ipcRenderer.invoke('dialog:open-save-file'),
  analyzeSave: (filePath) => ipcRenderer.invoke('save:analyze', filePath),
  // Settings
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (data) => ipcRenderer.invoke('settings:set', data),
});
