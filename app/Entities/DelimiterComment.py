from Entities.Tx import Tx

class DelimiterComment:
    def __init__(self, delimiter_text: str):
        self._start: str
        self._end: str

        if not delimiter_text or delimiter_text.isspace():
            raise ValueError("Delimiter cannot be null, empty, or whitespace.")

        self._start = f"{Tx.COMMENT_TAG_STARTING} {delimiter_text}{Tx.START_SUFFIX} {Tx.COMMENT_TAG_ENDING}"
        self._end = f"{Tx.COMMENT_TAG_ENDING} {delimiter_text}{Tx.END_SUFFIX} {Tx.COMMENT_TAG_ENDING}"

    @property
    def start(self) -> str:
        return self._start

    @property
    def end(self) -> str:
        return self._end

    def __str__(self) -> str:
        return (
            self._start
            .replace(Tx.COMMENT_TAG_STARTING, "")
            .replace(Tx.COMMENT_TAG_ENDING, "")
            .replace(Tx.START_SUFFIX, "")
            .strip()
        )