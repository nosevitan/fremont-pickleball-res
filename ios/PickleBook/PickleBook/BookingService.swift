// BookingService.swift
// PickleBook
//
// Async network client for the PickleBook toggle server.

import Foundation

// MARK: - Booking Service

actor BookingService {
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        self.session = URLSession(configuration: config)
    }

    // MARK: - Helpers

    private func baseURL() -> String {
        UserDefaults.standard.string(forKey: "serverURL")
            ?? "http://192.168.1.100:8787"
    }

    private func url(for path: String) -> URL {
        URL(string: "\(baseURL())\(path)")!
    }

    // MARK: - GET requests

    func fetchStatus() async throws -> BookingStatus {
        let (data, _) = try await session.data(from: url(for: "/status"))
        return try JSONDecoder().decode(BookingStatus.self, from: data)
    }

    func fetchLogs() async throws -> [LogEntry] {
        let (data, _) = try await session.data(from: url(for: "/logs"))
        let response = try JSONDecoder().decode(LogsResponse.self, from: data)
        return response.logs
    }

    // MARK: - POST requests

    func toggle() async throws -> BookingStatus {
        var request = URLRequest(url: url(for: "/toggle"))
        request.httpMethod = "POST"
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(BookingStatus.self, from: data)
    }

    func setEnabled(_ enabled: Bool) async throws -> BookingStatus {
        let path = enabled ? "/enable" : "/disable"
        var request = URLRequest(url: url(for: path))
        request.httpMethod = "POST"
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(BookingStatus.self, from: data)
    }
}
