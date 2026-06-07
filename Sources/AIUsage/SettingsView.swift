import SwiftUI

struct SettingsView: View {
    @AppStorage("autoRefreshMinutes") private var interval = 60
    @AppStorage("showMenuBar") private var showMenuBar = true

    let intervals = [15, 30, 60, 120, 240]

    var body: some View {
        Form {
            Section("Refresh") {
                Picker("Auto-refresh every", selection: $interval) {
                    ForEach(intervals, id: \.self) { m in
                        Text("\(m) minutes").tag(m)
                    }
                }
            }
            Section("UI") {
                Toggle("Show in menu bar", isOn: $showMenuBar)
            }
        }
        .formStyle(.grouped)
        .padding()
        .frame(width: 360, height: 200)
        .onChange(of: interval) {
            NotificationCenter.default.post(name: UsageStore.refreshIntervalChangedNotification, object: nil)
        }
    }
}
