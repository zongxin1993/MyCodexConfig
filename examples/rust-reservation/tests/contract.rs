use reservation_fixture::{reserve, ReserveError};

#[test]
fn reservation_contract() {
    let capacity = 10;
    assert_eq!(reserve(capacity, 4), Ok(6));
    assert_eq!(reserve(capacity, 10), Ok(0));
    assert_eq!(reserve(capacity, 11), Err(ReserveError::Insufficient));
    assert_eq!(capacity, 10);
    assert_eq!(reserve(0, 0), Err(ReserveError::ZeroRequest));
    assert_eq!(reserve(u32::MAX, 1), Ok(u32::MAX - 1));
}
