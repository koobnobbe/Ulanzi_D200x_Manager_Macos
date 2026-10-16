// D200X Manager.app: a menu bar app that runs the manager (d200x_manager.py) from the project folder.
//
// The project folder is in Info.plist (D200XProjectDir), so the app runs the code as it is in git, with its
// .venv, config.yaml and profiles. The manager's output goes to ~/Library/Logs/D200X Manager.log. When the
// manager stops (no deck connected, a config error), it is started again after a few seconds.
// macOS asks for Accessibility (sending key presses) for this app, as it is the manager's parent.
import AppKit
import ServiceManagement

let webURL = URL(string: "http://127.0.0.1:8765")!
let restartDelay: TimeInterval = 10
let logURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/D200X Manager.log")

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let projectDir = Bundle.main.object(forInfoDictionaryKey: "D200XProjectDir") as? String ?? ""
    var texts: [String: String] = [:]
    var statusItem: NSStatusItem!
    var stateItem: NSMenuItem!
    var loginItem: NSMenuItem!
    var process: Process?
    var quitting = false
    var restartTimer: Timer?
    var startedAt = Date()

    func applicationDidFinishLaunching(_ notification: Notification) {
        texts = loadTexts()
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            let image = NSImage(systemSymbolName: "square.grid.3x3.fill", accessibilityDescription: "D200X Manager")
            image?.isTemplate = true
            button.image = image
        }
        let menu = NSMenu()
        menu.delegate = self
        stateItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
        stateItem.isEnabled = false
        menu.addItem(stateItem)
        menu.addItem(.separator())
        menu.addItem(item("open", #selector(openWeb), "o"))
        menu.addItem(item("restart", #selector(restart), "r"))
        menu.addItem(item("log", #selector(showLog), "l"))
        menu.addItem(item("folder", #selector(showFolder), ""))
        menu.addItem(.separator())
        loginItem = item("login", #selector(toggleLogin), "")
        menu.addItem(loginItem)
        menu.addItem(.separator())
        menu.addItem(item("quit", #selector(quit), "q"))
        statusItem.menu = menu
        start()
    }

    // Opening the app again (Finder, Spotlight, Launchpad) opens the web interface.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        openWeb()
        return false
    }

    func applicationWillTerminate(_ notification: Notification) {
        quitting = true
        stopManager()
    }

    func menuWillOpen(_ menu: NSMenu) {
        if let process = process, process.isRunning {
            stateItem.title = text("running")
        } else {
            stateItem.title = text("stopped")
        }
        loginItem.state = SMAppService.mainApp.status == .enabled ? .on : .off
    }

    // MARK: the manager process

    func start() {
        restartTimer?.invalidate()
        let python = projectDir + "/.venv/bin/python"
        guard FileManager.default.isExecutableFile(atPath: python) else {
            log("D200X Manager: no Python at \(python); run the installation in the project folder first.\n")
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = ["d200x_manager.py"]
        process.currentDirectoryURL = URL(fileURLWithPath: projectDir)
        var env = ProcessInfo.processInfo.environment
        env["PYTHONUNBUFFERED"] = "1"
        env["LANG"] = env["LANG"] ?? "en_US.UTF-8"
        process.environment = env
        if let handle = logHandle() {
            process.standardOutput = handle
            process.standardError = handle
        }
        process.terminationHandler = { [weak self] finished in
            DispatchQueue.main.async { self?.managerStopped(finished) }
        }
        log("\n=== \(Date()) start ===\n")
        do {
            try process.run()
            self.process = process
            startedAt = Date()
        } catch {
            log("D200X Manager: cannot start \(python): \(error)\n")
        }
    }

    func managerStopped(_ finished: Process) {
        guard finished === process else { return }
        process = nil
        log("=== \(Date()) stopped (exit \(finished.terminationStatus)) ===\n")
        if !quitting {
            restartTimer = Timer.scheduledTimer(withTimeInterval: restartDelay, repeats: false) { [weak self] _ in
                self?.start()
            }
        }
    }

    func stopManager() {
        guard let process = process, process.isRunning else { return }
        self.process = nil
        // SIGINT lets the manager stop as with Ctrl-C; if it hangs, end it
        kill(process.processIdentifier, SIGINT)
        let deadline = Date().addingTimeInterval(3)
        while process.isRunning && Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        }
        if process.isRunning { process.terminate() }
    }

    // MARK: menu actions

    @objc func openWeb() { NSWorkspace.shared.open(webURL) }

    @objc func restart() {
        stopManager()
        start()
    }

    @objc func showLog() {
        if !FileManager.default.fileExists(atPath: logURL.path) { log("") }
        NSWorkspace.shared.open(logURL)
    }

    @objc func showFolder() { NSWorkspace.shared.open(URL(fileURLWithPath: projectDir)) }

    @objc func toggleLogin() {
        do {
            if SMAppService.mainApp.status == .enabled {
                try SMAppService.mainApp.unregister()
            } else {
                try SMAppService.mainApp.register()
            }
        } catch {
            let alert = NSAlert()
            alert.messageText = text("login_failed")
            alert.informativeText = error.localizedDescription
            alert.runModal()
        }
    }

    @objc func quit() {
        quitting = true
        stopManager()
        NSApp.terminate(nil)
    }

    // MARK: helpers

    func item(_ key: String, _ action: Selector, _ shortcut: String) -> NSMenuItem {
        let item = NSMenuItem(title: text(key), action: action, keyEquivalent: shortcut)
        item.target = self
        return item
    }

    func text(_ key: String) -> String { texts[key] ?? key }

    /// The menu texts in the manager's language ("ui: language:" in config.yaml), from menu.json in the app.
    func loadTexts() -> [String: String] {
        guard let url = Bundle.main.url(forResource: "menu", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let all = try? JSONSerialization.jsonObject(with: data) as? [String: [String: String]] else { return [:] }
        var language = "en"
        if let config = try? String(contentsOfFile: projectDir + "/config.yaml", encoding: .utf8),
           let match = config.range(of: #"(?m)^\s+language:\s*['"]?([a-z]{2})"#, options: .regularExpression) {
            language = String(config[match].suffix(2))
        }
        return (all["en"] ?? [:]).merging(all[language] ?? [:]) { _, new in new }
    }

    func logHandle() -> FileHandle? {
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: logURL) else { return nil }
        handle.seekToEndOfFile()
        return handle
    }

    func log(_ message: String) {
        guard let handle = logHandle() else { return }
        handle.write(message.data(using: .utf8)!)
        try? handle.close()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)   // menu bar only, no Dock icon
app.run()
