from scripts.feature_harness import load_spec, next_feature


def main() -> None:
    feature = next_feature(load_spec())
    if feature is None:
        print("No executable feature.")
        return
    print(f"{feature['id']}: {feature['title']} [{feature['status']}]")


if __name__ == "__main__":
    main()
