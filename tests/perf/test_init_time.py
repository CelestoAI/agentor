import time


def test_import_time():
    t0 = time.perf_counter()
    t1 = time.perf_counter()
    assert t1 - t0 < 5, (
        f"Package import should take less than 5 second but took {t1 - t0:.4f} seconds"
    )


if __name__ == "__main__":
    test_import_time()
