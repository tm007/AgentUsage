// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "AIUsage",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "AIUsage", targets: ["AIUsage"])
    ],
    targets: [
        .executableTarget(
            name: "AIUsage"
        )
    ]
)
