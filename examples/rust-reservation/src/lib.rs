//! A dependency-free workflow validation fixture.
//! ```
//! use reservation_fixture::reserve;
//! assert_eq!(reserve(10, 4), Ok(6));
//! ```

#[derive(Debug, PartialEq, Eq)]
pub enum ReserveError {
    ZeroRequest,
    Insufficient,
}

/// Reserve a positive quantity without mutating caller state.
pub fn reserve(available: u32, requested: u32) -> Result<u32, ReserveError> {
    if requested == 0 {
        return Err(ReserveError::ZeroRequest);
    }
    available
        .checked_sub(requested)
        .ok_or(ReserveError::Insufficient)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_invalid_requests() {
        assert_eq!(reserve(10, 0), Err(ReserveError::ZeroRequest));
        assert_eq!(reserve(10, 11), Err(ReserveError::Insufficient));
    }
}
