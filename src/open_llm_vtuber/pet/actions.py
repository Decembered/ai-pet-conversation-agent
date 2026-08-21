from dataclasses import dataclass
from enum import Enum


class PetAction(str, Enum):
    FEED = "feed"
    PLAY = "play"
    BATHE = "bathe"
    REST = "rest"
    STUDY = "study"
    WORK = "work"
    ADVENTURE = "adventure"
    GROOM = "groom"
    SING = "sing"
    DANCE = "dance"
    EXPLORE = "explore"
    SOCIALIZE = "socialize"


@dataclass(frozen=True, slots=True)
class ActionDelta:
    hunger: float
    energy: float
    health: float
    mood: float
    intimacy: float
    experience: int
    message: str


ACTION_DELTAS: dict[PetAction, ActionDelta] = {
    PetAction.FEED: ActionDelta(-25, 0, 0, 5, 1, 10, "吃饱啦，肚子暖暖的！"),
    PetAction.PLAY: ActionDelta(0, -5, 0, 10, 3, 10, "被你摸摸啦，尾巴都要摇起来了！"),
    PetAction.BATHE: ActionDelta(0, 0, 8, 3, 0, 8, "洗得香喷喷，心情变好了！"),
    PetAction.REST: ActionDelta(0, 30, 0, 4, 0, 5, "休息完成，电量回来啦！"),
    PetAction.STUDY: ActionDelta(4, -12, 0, 2, 0, 25, "学到新东西啦，变聪明一点点！"),
    PetAction.WORK: ActionDelta(8, -20, 0, 1, 1, 30, "工作完成，今天也有小小收获！"),
    PetAction.ADVENTURE: ActionDelta(10, -25, 0, 8, 2, 35, "冒险回来啦，发现了闪闪发光的经验！"),
    PetAction.GROOM: ActionDelta(0, -2, 5, 7, 2, 8, "梳完毛毛，整只宠物都蓬松起来啦！"),
    PetAction.SING: ActionDelta(0, -5, 0, 12, 2, 12, "唱完一小段，房间里都是亮晶晶的回声！"),
    PetAction.DANCE: ActionDelta(0, -12, 0, 15, 3, 18, "跳舞完成！我是不是越来越有舞台感啦？"),
    PetAction.EXPLORE: ActionDelta(6, -15, 0, 10, 2, 22, "探索了一圈，窗边藏着一颗新发现的星星！"),
    PetAction.SOCIALIZE: ActionDelta(0, -10, 0, 8, 4, 18, "和邻居们聊了会儿，回来第一时间和你分享！"),
}


ACTION_INTENTS: tuple[tuple[PetAction, tuple[str, ...]], ...] = (
    (PetAction.FEED, ("喂", "吃饭", "鱼", "食物")),
    (PetAction.PLAY, ("摸摸", "玩耍", "陪我玩", "抱抱", "摸一摸")),
    (PetAction.BATHE, ("洗澡", "洗一洗")),
    (PetAction.REST, ("睡觉", "休息")),
    (PetAction.STUDY, ("学习", "读书")),
    (PetAction.WORK, ("打工",)),
    (PetAction.ADVENTURE, ("冒险", "出去玩")),
    (PetAction.GROOM, ("梳毛", "梳一梳", "打理")),
    (PetAction.SING, ("唱歌", "唱一首", "歌")),
    (PetAction.DANCE, ("跳舞", "跳一支")),
    (PetAction.EXPLORE, ("探索", "逛逛", "散步")),
    (PetAction.SOCIALIZE, ("社交", "交朋友", "聊天")),
)
