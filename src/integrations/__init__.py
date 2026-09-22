import asyncio
from .suwayomi import Suwayomi, SourceMangaType

async def main():
    suwayomi = Suwayomi()
    library = await suwayomi.getLibrary()
    for manga in library:
        print(manga.chapters)
    await suwayomi.close()


if __name__ == "__main__":
    asyncio.run(main())

