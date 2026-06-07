import SwiftUI

@main
struct AIUsageApp: App {
    @StateObject private var store = UsageStore()

    init() {
        NSApplication.shared.setActivationPolicy(.regular)
    }

    var body: some Scene {
        WindowGroup("AgentUsage") {
            ContentView()
                .environmentObject(store)
                .frame(minWidth: 960, minHeight: 640)
                .onAppear {
                    store.start()
                    NSApplication.shared.setActivationPolicy(.regular)
                    NSApplication.shared.unhide(nil)
                    NSApplication.shared.activate(ignoringOtherApps: true)
                }
        }
        .defaultSize(width: 1120, height: 760)
        .defaultPosition(.center)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Refresh") {
                    store.refresh()
                }
                .keyboardShortcut("r", modifiers: .command)
            }

            CommandGroup(replacing: .saveItem) {
                Button("Close Dashboard") {
                    NSApp.keyWindow?.close()
                }
                .keyboardShortcut("w", modifiers: .command)
            }
        }

        Settings {
            SettingsView()
        }
    }
}
