import SwiftUI
import Charts

struct DashboardView: View {
    @EnvironmentObject var store: UsageStore

    var body: some View {
        GeometryReader { geometry in
            let outerPadding: CGFloat = 28
            let contentHeight = max(720, geometry.size.height - outerPadding * 2)
            let topRowHeight: CGFloat = 108
            let rowGap: CGFloat = 22
            let upperRowHeight = max(260, contentHeight * 0.38)
            let lowerRowHeight = max(320, contentHeight - topRowHeight - upperRowHeight - rowGap * 2)

            ScrollView {
                Group {
                    if store.isMissingSummary {
                        EmptySummaryView(isRefreshing: store.isRefreshing) {
                            store.refresh()
                        }
                        .frame(maxWidth: .infinity, minHeight: 520)
                    } else {
                        VStack(alignment: .leading, spacing: rowGap) {
                            HStack(spacing: 14) {
                                StatCard(title: "Total Tokens", value: totalTokens, breakdown: tokenBreakdown)
                                StatCard(title: "Input", value: inputTokens, breakdown: inputBreakdown)
                                StatCard(title: "Cache", value: cacheTokens, breakdown: cacheBreakdown)
                                StatCard(title: "Output", value: outputTokens, breakdown: outputBreakdown)
                            }
                            .frame(height: topRowHeight)

                            HStack(alignment: .top, spacing: 24) {
                                DashboardPanel(title: "Daily Volume") {
                                    if let summary = store.summary, !summary.days.isEmpty {
                                        DailyVolumeChart(days: summary.days)
                                            .frame(maxHeight: .infinity)
                                    } else {
                                        ContentUnavailableView("No data", systemImage: "chart.bar")
                                            .frame(maxHeight: .infinity)
                                    }
                                }

                                DashboardPanel(title: "Tool Mix") {
                                    if let summary = store.summary, !summary.tools.isEmpty {
                                        ToolMixChart(tools: summary.tools)
                                            .frame(maxHeight: .infinity)
                                    } else {
                                        ContentUnavailableView("No data", systemImage: "chart.pie")
                                            .frame(maxHeight: .infinity)
                                    }
                                }
                            }
                            .frame(height: upperRowHeight)

                            HStack(alignment: .top, spacing: 24) {
                                DashboardPanel(title: "Top Projects") {
                                    TopProjectsTable(projects: store.summary?.projects.prefix(20) ?? [])
                                        .frame(maxHeight: .infinity)
                                }

                                DashboardPanel(title: "Calendar Heat") {
                                    CalendarHeatView(days: store.summary?.days ?? [])
                                        .frame(maxHeight: .infinity)
                                }
                            }
                            .frame(height: lowerRowHeight)

                            if let error = store.errorMessage {
                                Label(error, systemImage: "exclamationmark.triangle")
                                    .foregroundStyle(.red)
                                    .padding()
                                    .background(.ultraThinMaterial)
                                    .cornerRadius(8)
                            }
                        }
                        .frame(minHeight: contentHeight, alignment: .top)
                    }
                }
                .padding(outerPadding)
            }
        }
        .background(
            LinearGradient(
                colors: [Color(nsColor: .windowBackgroundColor), Color.cyan.opacity(0.08), Color.pink.opacity(0.05)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
    }

    var totalTokens: String {
        formatter(store.summary?.tools.reduce(0) { $0 + $1.totalTokens } ?? 0)
    }
    var inputTokens: String {
        formatter(store.summary?.tools.reduce(0) { $0 + $1.inputTokens } ?? 0)
    }
    var cacheTokens: String {
        let cc = store.summary?.tools.reduce(0) { $0 + $1.cacheCreationTokens } ?? 0
        let cr = store.summary?.tools.reduce(0) { $0 + $1.cacheReadTokens } ?? 0
        return formatter(cc + cr)
    }
    var outputTokens: String {
        formatter(store.summary?.tools.reduce(0) { $0 + $1.outputTokens } ?? 0)
    }

    var tokenBreakdown: [(String, Int)] {
        store.summary?.tools.map { ($0.tool, $0.totalTokens) } ?? []
    }
    var inputBreakdown: [(String, Int)] {
        store.summary?.tools.map { ($0.tool, $0.inputTokens) } ?? []
    }
    var cacheBreakdown: [(String, Int)] {
        store.summary?.tools.map { ($0.tool, $0.cacheCreationTokens + $0.cacheReadTokens) } ?? []
    }
    var outputBreakdown: [(String, Int)] {
        store.summary?.tools.map { ($0.tool, $0.outputTokens) } ?? []
    }
}

private let decimalFormatter: NumberFormatter = {
    let nf = NumberFormatter()
    nf.numberStyle = .decimal
    nf.maximumFractionDigits = 0
    return nf
}()

func formatter(_ value: Int) -> String {
    decimalFormatter.string(from: NSNumber(value: value)) ?? "0"
}

func pct(_ part: Int, of total: Int) -> String {
    guard total > 0 else { return "0%" }
    return String(format: "%.1f%%", Double(part) / Double(total) * 100)
}

struct StatCard: View {
    let title: String
    let value: String
    let breakdown: [(String, Int)]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.system(.title2, design: .rounded))
                    .fontWeight(.semibold)
                    .fontDesign(.monospaced)
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }

            StatBreakdownStrip(breakdown: breakdown)
                .frame(height: 8)
                .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
        .padding(.horizontal, 18)
        .background(.ultraThinMaterial)
        .cornerRadius(12)
        .help(breakdownSummary)
    }

    private var breakdownSummary: String {
        breakdown
            .sorted { $0.1 > $1.1 }
            .map { "\($0.0): \(formatter($0.1))" }
            .joined(separator: "\n")
    }
}

struct StatBreakdownStrip: View {
    let breakdown: [(String, Int)]

    private var visibleBreakdown: [(String, Int)] {
        breakdown
            .filter { $0.1 > 0 }
            .sorted { $0.1 > $1.1 }
    }

    var body: some View {
        let total = max(visibleBreakdown.reduce(0) { $0 + $1.1 }, 1)
        GeometryReader { geometry in
            HStack(spacing: 3) {
                ForEach(visibleBreakdown, id: \.0) { item in
                    RoundedRectangle(cornerRadius: 2, style: .continuous)
                        .fill(color(for: item.0).opacity(0.9))
                        .frame(width: max(4, geometry.size.width * CGFloat(item.1) / CGFloat(total)))
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .clipped()
        }
        .accessibilityHidden(true)
    }
}

struct DashboardPanel<Content: View>: View {
    let title: String
    let content: () -> Content

    init(title: String, @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)
            content()
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

struct EmptySummaryView: View {
    let isRefreshing: Bool
    let refresh: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.bar.doc.horizontal")
                .font(.system(size: 44))
                .foregroundStyle(.secondary)
            Text("No usage summary yet")
                .font(.title2.weight(.semibold))
            Text("Generate your first usage-summary.json from the existing Python scraper to populate the dashboard.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 440)
            Button {
                refresh()
            } label: {
                Label(isRefreshing ? "Running..." : "Run scraper now", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.borderedProminent)
            .disabled(isRefreshing)
        }
        .padding(32)
        .background(.ultraThinMaterial)
        .cornerRadius(12)
    }
}

struct DailyVolumeChart: View {
    let days: [DayMetrics]
    private let points: [DayToolPoint]
    @State private var selectedDay: String? = nil

    init(days: [DayMetrics]) {
        self.days = days
        self.points = days.flatMap { day -> [DayToolPoint] in
            var pts: [DayToolPoint] = []
            if let v = day.claude, v > 0 { pts.append(.init(day: day.day, tool: "Claude", value: v)) }
            if let v = day.codex, v > 0 { pts.append(.init(day: day.day, tool: "Codex", value: v)) }
            if let v = day.openCode, v > 0 { pts.append(.init(day: day.day, tool: "OpenCode", value: v)) }
            if let v = day.cursor, v > 0 { pts.append(.init(day: day.day, tool: "Cursor", value: v)) }
            if let v = day.hermes, v > 0 { pts.append(.init(day: day.day, tool: "Hermes", value: v)) }
            if let v = day.pi, v > 0 { pts.append(.init(day: day.day, tool: "Pi", value: v)) }
            return pts
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Group {
                if let selectedDay,
                   let dayMetrics = days.first(where: { $0.day == selectedDay }) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(selectedDay)
                            .font(.caption.bold())
                            .foregroundStyle(.secondary)
                        HStack(spacing: 12) {
                            if let v = dayMetrics.claude, v > 0 {
                                Text("Claude: \(formatter(Int(v)))")
                                    .foregroundStyle(Color.cyan)
                            }
                            if let v = dayMetrics.codex, v > 0 {
                                Text("Codex: \(formatter(Int(v)))")
                                    .foregroundStyle(Color.pink)
                            }
                            if let v = dayMetrics.openCode, v > 0 {
                                Text("OpenCode: \(formatter(Int(v)))")
                                    .foregroundStyle(Color.yellow)
                            }
                            if let v = dayMetrics.cursor, v > 0 {
                                Text("Cursor: \(formatter(Int(v)))")
                                    .foregroundStyle(Color.white)
                            }
                            if let v = dayMetrics.hermes, v > 0 {
                                Text("Hermes: \(formatter(Int(v)))")
                                    .foregroundStyle(Color.orange)
                            }
                            if let v = dayMetrics.pi, v > 0 {
                                Text("Pi: \(formatter(Int(v)))")
                                    .foregroundStyle(Color.purple)
                            }
                            Text("Total: \(formatter(Int(dayMetrics.total)))")
                                .fontWeight(.semibold)
                        }
                        .font(.caption)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                    }
                } else {
                    Text("Hover or drag to inspect a day")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(height: 34, alignment: .topLeading)

            Chart(points) {
                AreaMark(
                    x: .value("Day", $0.day),
                    y: .value("Tokens", $0.value)
                )
                .foregroundStyle(by: .value("Tool", $0.tool))
                .opacity(0.3)

                LineMark(
                    x: .value("Day", $0.day),
                    y: .value("Tokens", $0.value)
                )
                .foregroundStyle(by: .value("Tool", $0.tool))
                .lineStyle(StrokeStyle(lineWidth: 2))
                .symbol(by: .value("Tool", $0.tool))
            }
            .chartForegroundStyleScale([
                "Claude": Color.cyan, "Codex": Color.pink,
                "OpenCode": Color.yellow, "Cursor": Color.white,
                "Hermes": Color.orange, "Pi": Color.purple
            ])
            .chartXAxis(.hidden)
            .chartYAxis {
                AxisMarks(position: .leading)
            }
            .chartXSelection(value: $selectedDay)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .animation(.easeInOut(duration: 0.2), value: selectedDay)
    }
}

struct DayToolPoint: Identifiable {
    var id: String { "\(day)-\(tool)" }
    let day, tool: String
    let value: Double
}

struct ToolMixChart: View {
    let tools: [ToolSummary]
    private let totalTokens: Double
    private let pieData: [ToolPie]
    @State private var selectedTool: String? = nil

    init(tools: [ToolSummary]) {
        self.tools = tools
        self.totalTokens = Double(tools.reduce(0) { $0 + $1.totalTokens })
        self.pieData = tools.map { ToolPie(tool: $0.tool, value: Double($0.totalTokens)) }
    }

    var body: some View {
        Chart(pieData) {
            SectorMark(
                angle: .value("Tokens", $0.value),
                innerRadius: .ratio(0.55)
            )
            .foregroundStyle(by: .value("Tool", $0.tool))
            .opacity(selectedTool == nil || selectedTool == $0.tool ? 1 : 0.3)
        }
        .chartForegroundStyleScale([
            "Claude": Color.cyan, "Codex": Color.pink,
            "OpenCode": Color.yellow, "Cursor": Color.white,
            "Hermes": Color.orange, "Pi": Color.purple
        ])
        .chartAngleSelection(value: $selectedTool)
        .chartBackground { proxy in
            GeometryReader { geometry in
                if let selectedTool,
                   let tool = tools.first(where: { $0.tool == selectedTool }),
                   let plotFrame = proxy.plotFrame {
                    let value = Double(tool.totalTokens)
                    let percentage = totalTokens > 0 ? value / totalTokens * 100 : 0
                    let rect = geometry[plotFrame]
                    VStack(spacing: 2) {
                        Text(tool.tool)
                            .font(.caption.bold())
                            .foregroundStyle(color(for: tool.tool))
                        Text(formatter(tool.totalTokens))
                            .font(.callout.bold())
                            .fontDesign(.monospaced)
                        Text(String(format: "%.1f%%", percentage))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .position(
                        x: rect.midX,
                        y: rect.midY
                    )
                } else if let plotFrame = proxy.plotFrame {
                    let rect = geometry[plotFrame]
                    VStack(spacing: 2) {
                        Text("Total")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(formatter(Int(totalTokens)))
                            .font(.callout.bold())
                            .fontDesign(.monospaced)
                    }
                    .position(
                        x: rect.midX,
                        y: rect.midY
                    )
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .animation(.easeInOut(duration: 0.2), value: selectedTool)
    }
}

struct ToolPie: Identifiable {
    var id: String { tool }
    let tool: String
    let value: Double
}

struct TopProjectsTable: View {
    let projects: ArraySlice<ProjectSummary>
    @State private var sortOrder: [KeyPathComparator<ProjectSummary>] = [KeyPathComparator(\.totalTokens, order: .reverse)]

    var body: some View {
        Table(of: ProjectSummary.self, sortOrder: $sortOrder) {
            TableColumn("Project", value: \.project) { r in
                VStack(alignment: .leading, spacing: 1) {
                    Text(r.project)
                        .fontWeight(.medium)
                        .lineLimit(1)
                        .truncationMode(.tail)
                        .help(r.project)
                    Text("\(r.tool)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
            }
            TableColumn("Tokens", value: \.totalTokens) { r in
                Text(formatter(r.totalTokens))
                    .fontDesign(.monospaced)
                    .monospacedDigit()
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            TableColumn("Sessions", value: \.sessions) { r in
                Text("\(r.sessions)")
                    .fontDesign(.monospaced)
                    .monospacedDigit()
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
        } rows: {
            ForEach(Array(projects)) { r in
                TableRow(r)
            }
        }
        .frame(minHeight: 220, maxHeight: .infinity)
    }
}

struct CalendarHeatView: View {
    private let maxDays = 105
    private let recent: [DayMetrics]
    private let maxVal: Double
    @State private var selectedDay: DayMetrics? = nil

    init(days: [DayMetrics]) {
        self.recent = Array(days.suffix(maxDays))
        self.maxVal = max(recent.map(\.total).max() ?? 1, 1)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let day = selectedDay {
                CalendarCaption(day: day)
                    .frame(height: 34, alignment: .topLeading)
            } else {
                Text("Hover a cell to inspect a day")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(height: 34, alignment: .topLeading)
            }

            GeometryReader { geometry in
                let spacing: CGFloat = 4
                let columnCount = bestColumnCount(for: geometry.size, spacing: spacing)
                let rowCount = max(1, Int(ceil(Double(recent.count) / Double(columnCount))))
                let columns = Array(repeating: GridItem(.fixed(cellSize(for: geometry.size, columns: columnCount, rows: rowCount, spacing: spacing)), spacing: spacing), count: columnCount)
                let cell = cellSize(for: geometry.size, columns: columnCount, rows: rowCount, spacing: spacing)
                let gridWidth = cell * CGFloat(columnCount) + spacing * CGFloat(columnCount - 1)
                let gridHeight = cell * CGFloat(rowCount) + spacing * CGFloat(rowCount - 1)

                LazyVGrid(columns: columns, alignment: .leading, spacing: spacing) {
                    ForEach(0..<recent.count, id: \.self) { i in
                        let day = recent[i]
                        let intensity = day.total / maxVal
                        CalendarDayCell(day: day, intensity: intensity, isSelected: selectedDay?.day == day.day) { hovering in
                            withAnimation(.easeInOut(duration: 0.12)) {
                                selectedDay = hovering ? day : nil
                            }
                        }
                        .frame(width: cell, height: cell)
                    }
                }
                .frame(width: gridWidth, height: gridHeight, alignment: .topLeading)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private func bestColumnCount(for size: CGSize, spacing: CGFloat) -> Int {
        guard !recent.isEmpty else { return 1 }
        let maxColumns = min(maxDays, recent.count)
        var bestColumns = min(15, maxColumns)
        var bestScore: CGFloat = -1

        for columns in 7...max(7, maxColumns) {
            guard columns <= maxColumns else { continue }
            let rows = max(1, Int(ceil(Double(recent.count) / Double(columns))))
            let cell = cellSize(for: size, columns: columns, rows: rows, spacing: spacing)
            let gridWidth = cell * CGFloat(columns) + spacing * CGFloat(columns - 1)
            let gridHeight = cell * CGFloat(rows) + spacing * CGFloat(rows - 1)
            let widthUse = gridWidth / max(size.width, 1)
            let heightUse = gridHeight / max(size.height, 1)
            let balancePenalty = abs(widthUse - heightUse) * 0.18
            let score = min(widthUse, 1) * min(heightUse, 1) - balancePenalty
            if score > bestScore {
                bestScore = score
                bestColumns = columns
            }
        }

        return bestColumns
    }

    private func cellSize(for size: CGSize, columns: Int, rows: Int, spacing: CGFloat) -> CGFloat {
        let usableWidth = max(1, size.width - spacing * CGFloat(columns - 1))
        let usableHeight = max(1, size.height - spacing * CGFloat(rows - 1))
        return floor(min(usableWidth / CGFloat(columns), usableHeight / CGFloat(rows)))
    }
}

struct CalendarDayCell: View {
    let day: DayMetrics
    let intensity: Double
    let isSelected: Bool
    let onHoverChange: (Bool) -> Void

    var body: some View {
        RoundedRectangle(cornerRadius: 2)
            .fill(Color.cyan.opacity(0.15 + intensity * 0.85))
            .overlay(
                RoundedRectangle(cornerRadius: 2)
                    .stroke(isSelected ? Color.white.opacity(0.85) : Color.clear, lineWidth: 1.5)
            )
            .aspectRatio(1, contentMode: .fit)
            .onHover(perform: onHoverChange)
    }
}

struct CalendarCaption: View {
    let day: DayMetrics

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(day.day)
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            HStack(spacing: 12) {
                if let v = day.claude, v > 0 {
                    Text("Claude: \(formatter(Int(v)))")
                        .foregroundStyle(Color.cyan)
                }
                if let v = day.codex, v > 0 {
                    Text("Codex: \(formatter(Int(v)))")
                        .foregroundStyle(Color.pink)
                }
                if let v = day.openCode, v > 0 {
                    Text("OpenCode: \(formatter(Int(v)))")
                        .foregroundStyle(Color.yellow)
                }
                if let v = day.cursor, v > 0 {
                    Text("Cursor: \(formatter(Int(v)))")
                        .foregroundStyle(Color.white)
                }
                if let v = day.hermes, v > 0 {
                    Text("Hermes: \(formatter(Int(v)))")
                        .foregroundStyle(Color.orange)
                }
                if let v = day.pi, v > 0 {
                    Text("Pi: \(formatter(Int(v)))")
                        .foregroundStyle(Color.purple)
                }
                Text("Total: \(formatter(Int(day.total)))")
                    .fontWeight(.semibold)
            }
            .font(.caption)
            .lineLimit(1)
            .minimumScaleFactor(0.8)
        }
    }
}

struct ColoredLabelStyle: LabelStyle {
    let color: Color
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 4) {
            configuration.icon
                .foregroundStyle(color)
                .font(.system(size: 6))
            configuration.title
        }
    }
}

func color(for tool: String) -> Color {
    switch tool {
    case "Claude": return .cyan
    case "Codex": return .pink
    case "OpenCode": return .yellow
    case "Cursor": return .white
    case "Hermes": return .orange
    case "Pi": return .purple
    default: return .accentColor
    }
}
