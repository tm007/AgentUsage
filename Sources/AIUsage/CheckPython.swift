import Foundation

/// Validates environment before running the scraper
enum EnvCheck {
    static func validate() -> String? {
        let fm = FileManager.default
        let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first!
        let folder = docs.appendingPathComponent("ai-usage-dashboard.documents-copy")
        
        let script = folder.appendingPathComponent("generate_usage_dashboard.py")
        let json = folder.appendingPathComponent("usage-summary.json")
        
        if !fm.fileExists(atPath: script.path) {
            return "Python scraper not found at \(script.path). Put generate_usage_dashboard.py there first."
        }
        
        let pythonPath = "/usr/bin/env"
        if !fm.isExecutableFile(atPath: pythonPath) {
            return "Cannot find /usr/bin/env — Python may not be installed."
        }
        
        if !fm.fileExists(atPath: json.path) {
            // Not an error — will be created on first refresh
            return nil
        }
        
        return nil
    }
}
