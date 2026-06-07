import SwiftUI

struct ModelsView: View {
    @EnvironmentObject var store: UsageStore
    @State private var sortOrder: [KeyPathComparator<ModelSummary>] = [KeyPathComparator(\.sessions, order: .reverse)]

    var body: some View {
        VStack(spacing: 0) {
            if let models = store.summary?.models, !models.isEmpty {
                Table(of: ModelSummary.self, sortOrder: $sortOrder) {
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

                    TableColumn("Model", value: \.model) { r in
                        Text(r.model)
                            .fontWeight(.medium)
                            .lineLimit(1)
                            .truncationMode(.tail)
                            .help(r.model)
                    }
                    .width(min: 160, ideal: 300)

                    TableColumn("Sessions", value: \.sessions) { r in
                        Text("\(r.sessions)")
                            .fontDesign(.monospaced)
                            .monospacedDigit()
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .width(min: 70, ideal: 90)
                } rows: {
                    ForEach(sortedModels) { r in
                        TableRow(r)
                    }
                }
                .tableStyle(.bordered)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding(16)
            } else {
                ContentUnavailableView("No model data", systemImage: "cpu")
                    .frame(maxHeight: .infinity)
            }
        }
        .background(
            LinearGradient(
                colors: [Color(nsColor: .windowBackgroundColor), Color.cyan.opacity(0.04)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
    }

    private var sortedModels: [ModelSummary] {
        guard let models = store.summary?.models else { return [] }
        guard let first = sortOrder.first else { return models }
        switch first.keyPath {
        case \.sessions:
            return first.order == .forward ? models.sorted { $0.sessions < $1.sessions } : models.sorted { $0.sessions > $1.sessions }
        case \.tool:
            return first.order == .forward ? models.sorted { $0.tool < $1.tool } : models.sorted { $0.tool > $1.tool }
        case \.model:
            return first.order == .forward ? models.sorted { $0.model < $1.model } : models.sorted { $0.model > $1.model }
        default:
            return models
        }
    }
}
