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
            CommandGroup(replacing: .appInfo) {
                Button("About AgentUsage") {
                    NSApplication.shared.orderFrontStandardAboutPanel(options: [
                        .applicationName: "AgentUsage",
                        .applicationVersion: "1.0",
                        .version: "1",
                        .credits: NSAttributedString(
                            string: "Local-first AI usage analytics for macOS.\n\nGenerated reports stay local by default and raw prompts are not written to dashboard files.",
                            attributes: [.font: NSFont.systemFont(ofSize: 12)]
                        )
                    ])
                }
            }

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

        Window("About AgentUsage", id: "about-agentusage") {
            AboutView()
        }
        .windowResizability(.contentSize)

        Settings {
            SettingsView()
        }
    }
}
