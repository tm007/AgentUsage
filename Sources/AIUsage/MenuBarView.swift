import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var store: UsageStore
    @Environment(\.openWindow) private var openWindow
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let summary = store.summary {
                ToolBarsView(tools: summary.tools) { tool in
                    openWindow(id: "dashboard")
                    NSApplication.shared.activate(ignoringOtherApps: true)
                    dismiss()
                }
                Divider()
                HStack {
                    Text("Total")
                        .fontWeight(.bold)
                    Spacer()
                    Text(formatter(summary.tools.reduce(0) { $0 + $1.totalTokens }))
                        .fontWeight(.bold)
                        .fontDesign(.monospaced)
                        .monospacedDigit()
                }

                if !store.topSessions.isEmpty {
                    Divider()
                    Text("Top Sessions")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(store.topSessions) { session in
                            SessionBarRow(session: session)
                        }
                    }
                }
            } else {
                Text("No data yet")
                    .foregroundStyle(.secondary)
            }
            Divider()
            Button("Open Dashboard") {
                openWindow(id: "dashboard")
                NSApplication.shared.activate(ignoringOtherApps: true)
                dismiss()
            }
            Button("Refresh Now") { store.refresh() }
            Button("Quit") { NSApp.terminate(nil) }
            if let last = store.lastRefresh {
                Divider()
                Text("Updated \(last.formatted(.relative(presentation: .named)))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
        }
        .padding()
        .frame(width: 280)
        .onAppear {
            store.loadTopSessionsIfNeeded()
        }
    }
}

struct ToolBarsView: View {
    let tools: [ToolSummary]
    let onSelect: (String) -> Void

    var body: some View {
        let maxTokens = max(tools.map(\.totalTokens).max() ?? 1, 1)

        VStack(alignment: .leading, spacing: 8) {
            ForEach(tools) { tool in
                ToolBarRow(tool: tool, maxTokens: maxTokens, onSelect: onSelect)
            }
        }
    }
}

struct ToolBarRow: View {
    let tool: ToolSummary
    let maxTokens: Int
    let onSelect: (String) -> Void
    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(tool.tool)
                    .fontWeight(.medium)
                Spacer()
                Text(formatter(tool.totalTokens))
                    .fontDesign(.monospaced)
                    .monospacedDigit()
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(.secondary.opacity(0.18))
                    Capsule()
                        .fill(color(for: tool.tool))
                        .frame(width: proxy.size.width * CGFloat(tool.totalTokens) / CGFloat(maxTokens))
                }
            }
            .frame(height: 6)

            if isHovered {
                HStack(spacing: 8) {
                    Text("In: \(formatter(tool.inputTokens))")
                    Text("Out: \(formatter(tool.outputTokens))")
                    if tool.cacheReadTokens > 0 || tool.cacheCreationTokens > 0 {
                        Text("Cache: \(formatter(tool.cacheCreationTokens + tool.cacheReadTokens))")
                    }
                    Spacer()
                }
                .font(.caption2)
                .foregroundStyle(.secondary)
                .transition(.opacity)
            }
        }
        .font(.system(size: 13))
        .contentShape(Rectangle())
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
            .onTapGesture {
                onSelect(tool.tool)
            }
    }
}

struct SessionBarRow: View {
    let session: SessionRecord
    @State private var isHovered = false

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color(for: session.tool))
                .frame(width: 6, height: 6)
            VStack(alignment: .leading, spacing: 1) {
                Text(session.projectLabel.isEmpty ? "(unknown)" : session.projectLabel)
                    .font(.system(size: 12))
                    .lineLimit(1)
                    .truncationMode(.tail)
                Text(session.model.isEmpty ? session.tool : session.model)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
            Spacer()
            Text(formatter(session.totalTokens))
                .font(.system(size: 11, design: .monospaced))
                .monospacedDigit()
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
        .contentShape(Rectangle())
        .background(isHovered ? Color.secondary.opacity(0.1) : Color.clear)
        .cornerRadius(4)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.12)) {
                isHovered = hovering
            }
        }
    }
}
