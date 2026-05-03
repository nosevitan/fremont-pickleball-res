// Models.swift
// PickleBook
//
// Data models matching the FastAPI server responses.

import Foundation

// MARK: - Server Status

struct BookingStatus: Codable, Equatable {
    let enabled: Bool
    let nextBookingDate: String
    let lastRun: String?
    let lastResult: String?

    enum CodingKeys: String, CodingKey {
        case enabled
        case nextBookingDate = "next_booking_date"
        case lastRun = "last_run"
        case lastResult = "last_result"
    }
}

// MARK: - Log Response

struct LogEntry: Codable, Identifiable {
    let line: String
    var id: String { line }
}

struct LogsResponse: Codable {
    let logs: [LogEntry]
}
