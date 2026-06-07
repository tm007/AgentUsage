import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: UsageStore
    @State private var selectedTab = 0
    @State private var showingAbout = false

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.bar")
                }
                .tag(0)

            SessionsView()
                .tabItem {
                    Label("Chats", systemImage: "bubble.left.and.bubble.right")
                }
                .tag(1)

            ModelsView()
                .tabItem {
                    Label("Models", systemImage: "cpu")
                }
                .tag(2)
        }
        .padding(.top, 8)
        .toolbar {
            ToolbarItem {
                Button(action: { store.refresh() }) {
                    Image(systemName: store.isRefreshing ? "arrow.clockwise.circle.fill" : "arrow.clockwise.circle")
                }
                .disabled(store.isRefreshing)
            }
            ToolbarItem {
                Button(action: { exportData() }) {
                    Image(systemName: "square.and.arrow.up")
                }
                .disabled(store.summary == nil)
                .help("Export usage data as JSON")
            }
            ToolbarItem {
                Button(action: { showingAbout = true }) {
                    Image(systemName: "info.circle")
                }
                .help("About AgentUsage")
            }
            ToolbarItem {
                if let last = store.lastRefresh {
                    Text("Updated \(last.formatted(.relative(presentation: .named)))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .monospacedDigit()
                }
            }
        }
        .sheet(isPresented: $showingAbout) {
            AboutView()
        }
        .navigationTitle("AgentUsage")
    }

    private func exportData() {
        guard let summary = store.summary else { return }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = "ai-usage-export.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = .prettyPrinted
            let data = try encoder.encode(summary)
            try data.write(to: url)
        } catch {
            store.errorMessage = "Export failed: \(error.localizedDescription)"
        }
    }
}
