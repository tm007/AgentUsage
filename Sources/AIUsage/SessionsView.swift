import SwiftUI

struct SessionsView: View {
    @EnvironmentObject var store: UsageStore
    @State private var searchText = ""
    @State private var sortOrder: [KeyPathComparator<SessionRecord>] = [KeyPathComparator(\.totalTokens, order: .reverse)]

    private var filteredSessions: [SessionRecord] {
        let sessions = store.sessions
        guard !searchText.isEmpty else { return sessions }
        let lower = searchText.lowercased()
        return sessions.filter {
            $0.projectLabel.lowercased().contains(lower) ||
            $0.model.lowercased().contains(lower) ||
            $0.tool.lowercased().contains(lower) ||
            $0.sessionId.lowercased().contains(lower)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(.secondary)
                TextField("Search by project, model, tool or session ID", text: $searchText)
                    .textFieldStyle(.plain)
                if !searchText.isEmpty {
                    Button(action: { searchText = "" }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(10)
            .background(.ultraThinMaterial)
            .cornerRadius(8)
            .padding([.horizontal, .top], 16)

            if store.isLoadingSessions {
                ProgressView("Loading sessions…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if store.sessions.isEmpty {
                ContentUnavailableView("No sessions", systemImage: "bubble.left.and.exclamationmark.bubble.right")
                    .frame(maxHeight: .infinity)
            } else {
                Table(of: SessionRecord.self, sortOrder: $sortOrder) {
                    TableColumn("Tool", value: \.tool) { r in
                        HStack(spacing: 6) {
                            Circle()
                                .fill(color(for: r.tool))
                                .frame(width: 8, height: 8)
                            Text(r.tool)
                                .fontWeight(.medium)
                        }
                    }
                    .width(min: 60, ideal: 80)

                    TableColumn("Project", value: \.projectLabel) { r in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(r.projectLabel.isEmpty ? "(unknown)" : r.projectLabel)
                                .fontWeight(.medium)
                                .lineLimit(1)
                                .truncationMode(.tail)
                            if !r.projectPath.isEmpty {
                                Text(r.projectPath)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                                    .truncationMode(.middle)
                            }
                        }
                    }
                    .width(min: 120, ideal: 200)

                    TableColumn("Model", value: \.model) { r in
                        Text(r.model.isEmpty ? "n/a" : r.model)
                            .lineLimit(1)
                            .truncationMode(.tail)
                            .help(r.model)
                    }
                    .width(min: 100, ideal: 160)

                    TableColumn("Total", value: \.totalTokens) { r in
                        Text(formatter(r.totalTokens))
                            .fontDesign(.monospaced)
                            .monospacedDigit()
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .width(min: 70, ideal: 90)

                    TableColumn("Input", value: \.inputTokens) { r in
                        Text(formatter(r.inputTokens))
                            .fontDesign(.monospaced)
                            .monospacedDigit()
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .width(min: 70, ideal: 90)

                    TableColumn("Cache", value: \.cacheReadTokens) { r in
                        Text(formatter(r.cacheCreationTokens + r.cacheReadTokens))
                            .fontDesign(.monospaced)
                            .monospacedDigit()
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .width(min: 70, ideal: 90)

                    TableColumn("Output", value: \.outputTokens) { r in
                        Text(formatter(r.outputTokens))
                            .fontDesign(.monospaced)
                            .monospacedDigit()
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .width(min: 70, ideal: 90)

                    TableColumn("Date", value: \.day) { r in
                        Text(r.day)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .width(min: 70, ideal: 90)
                } rows: {
                    ForEach(sortedSessions) { r in
                        TableRow(r)
                    }
                }
                .tableStyle(.bordered)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding([.horizontal, .bottom], 16)
            }
        }
        .background(
            LinearGradient(
                colors: [Color(nsColor: .windowBackgroundColor), Color.cyan.opacity(0.04)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .onAppear {
            store.loadSessionsIfNeeded()
        }
    }

    private var sortedSessions: [SessionRecord] {
        let base = filteredSessions
        guard let first = sortOrder.first else { return base }
        switch first.keyPath {
        case \.totalTokens:
            return first.order == .forward ? base.sorted { $0.totalTokens < $1.totalTokens } : base.sorted { $0.totalTokens > $1.totalTokens }
        case \.inputTokens:
            return first.order == .forward ? base.sorted { $0.inputTokens < $1.inputTokens } : base.sorted { $0.inputTokens > $1.inputTokens }
        case \.outputTokens:
            return first.order == .forward ? base.sorted { $0.outputTokens < $1.outputTokens } : base.sorted { $0.outputTokens > $1.outputTokens }
        case \.tool:
            return first.order == .forward ? base.sorted { $0.tool < $1.tool } : base.sorted { $0.tool > $1.tool }
        case \.day:
            return first.order == .forward ? base.sorted { $0.day < $1.day } : base.sorted { $0.day > $1.day }
        default:
            return base
        }
    }
}
