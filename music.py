# import
from discord.ext import commands
import aiohttp, asyncio, discord, isodate, json, os, pprint, random, re, sys, time, traceback2, youtube_dl


# YTDL
class YTDLSource(discord.PCMVolumeTransformer):
    with open("./INFO.json") as F:
        info = json.load(F)
    ytdl = youtube_dl.YoutubeDL(info["ytdl_format_options"])
    ffmpeg_options = info["ffmpeg_options"]
    beforeOps = info["beforeOps"]

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: cls.ytdl.extract_info(url, download=not stream))
        filename = data['url'] if stream else cls.ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **cls.ffmpeg_options, before_options=cls.beforeOps), data=data)


# class
class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot  # type: commands.Bot
        self.playlist = {}
        self.status = {}
        self.music_skiped = []
        self.disconnected = []
        with open("./INFO.json") as F:
            info = json.load(F)
        self.info = info
        self.list = re.compile('[a-zA-Z0-9_-]{34}')
        self.vid = re.compile('[a-zA-Z0-9_-]{11}')
        youtube_dl.utils.bug_reports_message = lambda: ''
        with open("./TOKEN.json") as F:
            tokens = json.load(F)
        self.YOUTUBE_API = tokens["YOUTUBE_API"]
        self.API_INDEX = tokens["API_INDEX"]
        self.load_roles()

    def save_tokens(self):
        """
        YOUTUBE_APIを保存
        :return:
        """
        with open("./TOKEN.json") as F:
            tokens = json.load(F)
        tokens["API_INDEX"] = self.API_INDEX
        tokens["YOUTUBE_API"] = self.YOUTUBE_API
        with open("./TOKEN.json", 'w') as F:
            json.dump(tokens, F, indent=2)

    def check_url(self, url):
        """
        URLまたは曲名を認識
        :param url: 対称の文字列
        :return: [コード, 結果]
                0...間違ったURL
                1...動画idを検出, 動画id
                2...プレイリストidを検出, プレイリストid
                3...曲名を検出, 曲名
        """
        if url.startswith("https://youtu.be/") or url.startswith("https://youtube.com/") or url.startswith(
                "https://m.youtube.com/") or url.startswith("https://www.youtube.com/") or url.startswith(
                "http://youtu.be/") or url.startswith("http://youtube.com/") or url.startswith(
                "http://m.youtube.com/") or url.startswith("http://www.youtube.com/"):
            match = re.search(self.list, url)
            if match is None:
                vid_id = re.search(self.vid, url)
                if vid_id is None:
                    return [0, 0]  # 間違ったURL
                else:
                    return [1, vid_id.group()]  # 動画 - 動画id
            else:
                return [2, match.group()] # プレイリスト - プレイリストid
        elif url.startswith("http://") or url.startswith("https://"):
            return [0, 1]  # サポートされていないURL
        else:
            return [3, url]  # 曲名 - 曲名

    def get_day(self, txt):
        """
        日付を変換
        :param txt: 日付
        :return: 変形された日付
        """
        txt_day = txt.split("T")
        return txt_day[0].replace("-", "/")

    def load_roles(self):
        """
        役職,権限を更新
        :return:
        """
        with open("./ROLE.json") as F:
            roles = json.load(F)
        self.ADMIN = roles["ADMIN"]
        self.Contributor = roles["Contributor"]
        self.BAN = roles["BAN"]

    def return_duration(self, item):
        """
        YouTubeデータから動画の時間に変換
        :param item: YouTubeデータ
        :return: 動画の時間
        """
        if item['snippet']['liveBroadcastContent'] == "live":
            return "LIVE"
        else:
            return str(isodate.parse_duration(item['contentDetails']['duration']))

    async def initialize_data(self, ctx):
        """
        playlist, statusの初期化 & ボイスチャンネルへの接続,移動
        :param ctx: Context
        :return: 0...ボイスチャンネル接続に失敗
                 1...ボイスチャンネル接続に成功
                 2...ボイスチャンネル移動
                 3...ボイスチャンネルにすでに接続済
                 4...処理拒否
        """
        # 処理中でないか確認する
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return 4

        # BOTがVCに接続していない場合 .. .接続
        if ctx.voice_client is None:
            self.playlist[ctx.guild.id] = []
            self.status[ctx.guild.id] = {
                "loop": False,
                "repeat": False,
                "auto": False,
                "volume": 100,
                "channel": ctx.channel.id,
                "status": 0
            }
            try:
                await ctx.author.voice.channel.connect(timeout=10.0)
                return 1
            except:  # 接続に失敗
                await self.send_text(ctx, "FAILED_CONNECT")
                return 0

        # 送信者がVCに接続していない場合
        elif ctx.author.voice is None:
            await self.send_text(ctx, "JOIN_VC_BEFORE_PLAY")
            return 0

        # BOTと送信者のVCが異なる場合 ... 移動
        elif ctx.author.voice.channel != ctx.voice_client.channel:
            try:
                await ctx.voice_client.move_to(ctx.author.voice.channel)
                return 2
            except:  # 接続に失敗
                await self.send_text(ctx, "FAILED_CONNECT")
                return 0

        # BOTと送信者のVCが同じの場合
        else:
            return 3

    async def clean_all(self, ctx, report=False):
        try:
            self.disconnected.append(ctx.guild.id)
            if ctx.voice_client is None:
                pass
            elif ctx.voice_client.source is not None:
                ctx.voice_client.source.cleanup()
                await ctx.voice_client.disconnect()
            else:
                await ctx.voice_client.disconnect()
            if ctx.guild.id in self.disconnected:
                self.disconnected.remove(ctx.guild.id)
            self.playlist[ctx.guild.id] = []
            self.status[ctx.guild.id] = {
                "loop": False,
                "repeat": False,
                "auto": False,
                "volume": 100,
                "channel": ctx.channel.id,
                "status": 0
            }
            if report:
                await self.send_text(ctx, "ABNORMAL_SITUATION_DETECTED")
                return await self.report_error(ctx, "play_after", "異常な状況が検知されました:\nプレイリスト:{}\nステータス:{}".format(
                    pprint.pformat(self.playlist[ctx.guild.id]), pprint.pformat(self.status[ctx.guild.id])
                ))
        except:
            await self.send_text(ctx, "UNKNOWN_ERROR")
            await self.report_error(ctx, "clean_all", traceback2.format_exc())

    async def send_text(self, ctx, code, arg1=None, arg2=None):
        """
        言語問題を自動的に解決してメッセージを送信
        :param ctx: Context
        :param code: テキストコード
        :param arg1: 引数1(引数が必要な場合のみ)
        :param arg2: 引数2(引数が必要な場合のみ)
        :return: msg_obj(必要な場合のみ)
        """
        if code == "AUTO_MODE_ON":
            if str(ctx.guild.region) == "japan":
                await ctx.send(
                    ":warning:`オート再生モードが有効なので曲を追加できません.オフにするには`{}auto off`を使用してください.`".format(self.info["PREFIX"]))
            else:
                await ctx.send(
                    ":warning:`You can't add music because auto mode turn on. To turn off auto mode, please use`{}auto off".format(
                        self.info["PREFIX"]))
        elif code == "WRONG_URL":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`誤った形式のURLです.`")
            else:
                await ctx.send(":warning:`Sorry Wrong URL.`")
        elif code == "UNKNOWN_ERROR":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`不明なエラーが発生しました.`")
            else:
                await ctx.send(":warning:`Unknown error has occured.`")
        elif code == "NOT_SUPPORTED":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`このURLはサポートされていません.`")
            else:
                return await ctx.send(":warning:`Sorry This URL is not suporrted.`")
        elif code == "NO_APPROPRIATE":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`該当する曲がありませんでした.`")
            else:
                return await ctx.send(":warning:`There are no appropriate song.`")
        elif code == "NOT_ENOUGH":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`十分な検索結果がありませんでした.`")
            else:
                return await ctx.send(":warning:`There are not enough results.`")
        elif code == "FAILED_CONNECT":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`ボイスチャンネルに接続できませんでした.権限等を確認してください.`")
            else:
                return await ctx.send(":warning:`Connecting failed.Please check permission etc.`")
        elif code == "ALREADY_CONNECTED":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`すでにボイスチャンネルに接続しています.`")
            else:
                return await ctx.send(":warning:`Already connected to VC.`")
        elif code == "SOMETHING_WENT_WRONG_WHEN_LOADING_MUSIC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`動画の読み込み中にエラーが発生しました.`")
            else:
                await ctx.send(":warning:`Something went wrong when playing music.`")
        elif code == "PROCESS_TIMEOUT":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`一定時間内に選ばれなかったのでプロセスを終了しました`")
            else:
                await ctx.send(":warning:`process timeouted`")
        elif code == "INVALID_NUMBER":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`無効な番号です`")
            else:
                await ctx.send(":warning:`Invalid number`")
        elif code == "YOUR_ACCOUNT_BANNED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`あなたはBANされているため,使用できません.\n異議申し立ては公式サーバーにてお願いします.`")
                raise commands.CommandError("Your Account Banned")
            else:
                await ctx.send(
                    ":warning:`You cannnot use because you are banned.\nFor objection please use Official Server.`")
                raise commands.CommandError("Your Account Banned")
        elif code == "JOIN_VC_BEFORE_PLAY":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`まずボイスチャンネルに参加してください!`")
            else:
                await ctx.send(":warning:`Please enter voice channel before playing music`")
        elif code == "WRONG_COMMAND":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`コマンドが間違っています.構文が正しいことを確認してください!`")
            else:
                await ctx.send(":warning:`Wrong command.Please check your arguments are valid!`")
        elif code == "SKIPPED":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":white_check_mark: `スキップしました`")
            else:
                return await ctx.send(":white_check_mark: `Skipped`")
        elif code == "CONNECTED_TO_VC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`ボイスチャンネルに接続しました`")
            else:
                await ctx.send(":white_check_mark:`Connected to voice channel`")
        elif code == "MOVED_VC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`ボイスチャンネルを移動しました`")
            else:
                await ctx.send(":white_check_mark:`Moved to voice channel`")
        elif code == "NOT_PLAYING_MUSIC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`BOTは音楽を再生していません`")
            else:
                await ctx.send(":warning:`BOT is not playing music`")
        elif code == "DISCONNECTED_FROM_VC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`ボイスチャンネルから切断しました`")
            else:
                await ctx.send(":warning:`Disconnected from voice channel`")
        elif code == "CLEARED_MUSIC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`予約された曲を全て削除しました`")
            else:
                await ctx.send(":white_check_mark:`Removed all reserved music`")
        elif code == "WRONG_INDEX":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`指定したインデックスに対応する音楽がありません`")
            else:
                return await ctx.send(":warning:`There is no music to specified index`")
        elif code == "VALUE_LESS_THAN_0":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`0未満の値を指定することはできません`")
            else:
                return await ctx.send(":warning:`You can't specify a value less than 0`")
        elif code == "YOU_CANT_REMOVE_CURRENTLY_MUSIC":
            if str(ctx.guild.region) == "japan":
                return await ctx.send(":warning:`現在再生中の音楽を削除する場合は`{}skip`を使用してください`".format(self.info["PREFIX"]))
            else:
                return await ctx.send(":warning:`To remove music that is currently playing please use `{}skip".format(self.info["PREFIX"]))
        elif code == "VOLUME_CHANGED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`{}%に音量を変更しました`".format(arg1))
            else:
                await ctx.send(":white_check_mark:`Changed volume to {}%`".format(arg1))
        elif code == "REPEAT_OFF":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`repeat機能をオフにしました`")
            else:
                await ctx.send(":white_check_mark:`Turn off repeat mode`")
        elif code == "REPEAT_ON":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`repeat機能をオンにしました`")
            else:
                await ctx.send(":white_check_mark:`Turn on repeat mode`")
        elif code == "LOOP_OFF":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`loop機能をオフにしました`")
            else:
                await ctx.send(":white_check_mark:`Turn off loop mode`")
        elif code == "LOOP_ON":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`loop機能をオンにしました`")
            else:
                await ctx.send(":white_check_mark:`Turn on loop mode`")
        elif code == "RESUMED_MUSIC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`音楽の再生を再開しました`")
            else:
                await ctx.send(":white_check_mark:`Resumed playing music`")
        elif code == "ALREADY_RESUMED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`既に再開しています`")
            else:
                await ctx.send(":warning:`Already resumed`")
        elif code == "PAUSED_MUSIC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`音楽の再生を一時停止しました`")
            else:
                await ctx.send(":white_check_mark:`Paused playing music`")
        elif code == "ALREADY_PAUSED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`既に一時停止されています`")
            else:
                await ctx.sebd(":warning:`Already paused`")
        elif code == "AUTO_ENABLED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`オート再生モードをオンにしました.検索ワード「{}」`".format(arg1))
            else:
                await ctx.send(":white_check_mark:`Turn on auto mode. Search query「{}」`".format(arg1))
        elif code == "AUTO_ALREADY_OFF":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`オート再生モードは既にオフにです`")
            else:
                await ctx.send(":warning:`Already auto mode off`")
        elif code == "AUTO_OFF":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":white_check_mark:`オート再生モードをオフにしました`")
            else:
                await ctx.send(":white_check_mark:`Turn off auto mode`")
        elif code == "MUSIC_ADDED":
            if str(ctx.guild.region) == "japan":
                embed = discord.Embed(title=arg1["title"], url=arg1["url"], color=0x93ffab)
                embed.set_author(name="曲を追加しました")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="チャンネル", value=arg1['channel'])
                embed.add_field(name="アップロード", value=arg1['publish'])
                embed.add_field(name="動画時間", value=arg1['duration'])
                embed.add_field(name="リクエスト", value="    {}".format(arg1["user"]))
            else:
                embed = discord.Embed(title=arg1["title"], url=arg1["url"], color=0x93ffab)
                embed.set_author(name="Music added")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="Channel", value=arg1['channel'])
                embed.add_field(name="Upload", value=arg1['publish'])
                embed.add_field(name="Duration", value=arg1['duration'])
                embed.add_field(name="Requested by", value="    {}".format(arg1["user"]))
            await ctx.send(embed=embed)
        elif code == "PLAYLIST_ADDED":
            if str(ctx.guild.region) == "japan":
                embed = discord.Embed(title=arg1["title"] + "\n...等 {}曲".format(str(arg2)), url=arg1["url"],
                                      color=0x93ffab)
                embed.set_author(name="曲を追加しました")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="チャンネル", value=arg1['channel'])
                embed.add_field(name="アップロード", value=arg1['publish'])
                embed.add_field(name="動画時間", value=arg1['duration'])
                embed.add_field(name="リクエスト", value="    {}".format(arg1["user"]))
            else:
                embed = discord.Embed(title=arg1["title"] + "\n etc... {}songs".format(str(arg2)),
                                      url=arg1["url"], color=0x93ffab)
                embed.set_author(name="Music added")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="Channel", value=arg1['channel'])
                embed.add_field(name="Upload", value=arg1['publish'])
                embed.add_field(name="Duration", value=arg1['duration'])
                embed.add_field(name="Requested by", value="    {}".format(arg1["user"]))
            await ctx.send(embed=embed)
        elif code == "MUSIC_PLAY_NOW":
            if str(ctx.guild.region) == "japan":
                embed = discord.Embed(title=arg1["title"], url=arg1["url"], color=0xff82b2)
                embed.set_author(name="再生中")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="チャンネル", value=arg1['channel'])
                embed.add_field(name="アップロード", value=arg1['publish'])
                embed.add_field(name="動画時間", value=arg1['duration'])
                embed.add_field(name="リクエスト", value="    {}".format(arg1["user"]))
            else:
                embed = discord.Embed(title=arg1["title"], url=arg1["url"], color=0xff82b2)
                embed.set_author(name="Now playing")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="Channel", value=arg1['channel'])
                embed.add_field(name="Upload", value=arg1['publish'])
                embed.add_field(name="Duration", value=arg1['duration'])
                embed.add_field(name="Requested by", value="    {}".format(arg1["user"]))
            msg_obj = await ctx.send(embed=embed)
            return msg_obj
        elif code == "MUSIC_REMOVED":
            embed = discord.Embed(title=arg1["title"], url=arg1["url"], color=0xff9872)
            if str(ctx.guild.region) == "japan":
                embed.set_author(name="曲を削除しました")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="チャンネル", value=arg1['channel'])
                embed.add_field(name="アップロード", value=arg1['publish'])
                embed.add_field(name="動画時間", value=arg1['duration'])
                embed.add_field(name="リクエスト", value="    {}".format(arg1["user"]))
            else:
                embed.set_author(name="Music deleted")
                embed.set_thumbnail(url=arg1["thumbnail"])
                embed.add_field(name="Channel", value=arg1['channel'])
                embed.add_field(name="Upload", value=arg1['publish'])
                embed.add_field(name="Duration", value=arg1['duration'])
                embed.add_field(name="Requested by", value="    {}".format(arg1["user"]))
            await ctx.send(embed=embed)
        elif code == "DISCONNECTED_BECAUSE_ALL_USERS_LEFT":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`すべてのユーザーが接続を切ったためボイスチャンネルから切断しました`")
            else:
                await ctx.send(":warning:`Disconnected from voice channel because all users left`")
        elif code == "ABNORMAL_SITUATION_DETECTED":
            if str(ctx.guild.region) == "japan":
                await ctx.send("異常な状況が検知されたため,情報をクリアしました.")
            else:
                await ctx.send("Information was cleared because an abnormal situation was detected.")
        elif code == "SOMETHING_WENT_WRONG_WITH_TITLE":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`曲の再生中に問題が発生しました.他の物を試すか,{}autoを使用して再生してください.\n曲名:{}`".format(self.info["PREFIX"], arg1))
            else:
                await ctx.send(":warning:`Something went wrong when playing music.Please try another one or use {}auto to play.\nMusicName:{}`".format(self.info["PREFIX"], arg1))
        elif code == "OPERATION_DENIED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`曲の再生準備中にコマンドが実行されたため、操作が拒否されました.再生準備が完了したあとに再度試してください.\n( muffinが入力中... となっている場合は曲の再生準備中です.)`")
            else:
                await ctx.send(":warning:`The operation was rejected because a command was executed while preparing next song. Please try again after the song is ready to play.\n( muffin is typing... If so, the song is preparing.)`")

    async def report_error(self, ctx, name, message):
        """
        エラーをログチャンネルに送信
        :param ctx: Context
        :param name: 関数名
        :param message: エラーメッセージ
        :return:
        """
        channel = self.bot.get_channel(self.info["ERROR_CHANNEL"])
        embed = discord.Embed(title=name, description=message)
        embed.set_author(name="Error Reporter")
        await channel.send(embed=embed)

    async def get_request(self, url, ctx):
        """
        APIから情報を取得してデータを返す
        :param url: APIのURL
        :param ctx: Context
        :return: レスポンスデータ
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url + self.YOUTUBE_API[str(self.API_INDEX)]) as r:
                response = await r.json()
                if r.status == 200:
                    return [1, response]
                elif r.status == 403:
                    if int(self.API_INDEX) != 10:
                        self.API_INDEX += 1
                    else:
                        self.API_INDEX = 1
                    self.save_tokens()
                    await self.report_error(ctx, "get_request", "API_INDEXを{}に変更しました".format(self.API_INDEX))
                    async with aiohttp.ClientSession() as session2:
                        async with session2.get(url + self.YOUTUBE_API[str(self.API_INDEX)]) as r2:
                            response2 = await r2.json()
                            if r2.status == 200:
                                return [1, response2]
                            elif r2.status == 403:
                                await self.report_error(ctx, "get_request", "APIの問題を解決できません.youtube_dlの更新を試してください.")
                                return [0, r2.status, response2]
                            else:
                                return [0, r2.status, response2]
                else:
                    return [0, r.status, response]

    async def play_after(self, ctx):
        """
        曲の再生が終わった後の処理
        :param ctx: Context
        :return:
        """
        try:
            # 処理中の場合
            if ctx.guild.id in self.status:
                if self.status[ctx.guild.id]["status"] != 3:
                    self.status[ctx.guild.id]["status"] = 3
                else:
                    await self.report_error(ctx, "play_after", "play_after開始時にすでに処理中になっている事案が発生しました.現在この場合も処理を実行することになっていますが、必要に応じてはじくように設定してください.")
            elif self.playlist[ctx.guild.id] == []:
                return await self.clean_all(ctx, report=True)
            else:
                return await self.clean_all(ctx, report=True)
            if ctx.guild.id in self.disconnected:  # 切断の場合 - 次の曲の再生を防ぐ
                return self.disconnected.remove(ctx.guild.id)
            elif ctx.guild.id in self.music_skiped:  # スキップの場合 - 強制的に0番目の曲を削除
                self.music_skiped.remove(ctx.guild.id)
                if not self.status[ctx.guild.id]["auto"]:
                    self.playlist[ctx.guild.id].pop(0)
            else:
                if self.playlist[ctx.guild.id] == []:
                    return await self.clean_all(ctx, report=True)
                elif "time" not in self.playlist[ctx.guild.id][0] or "msg_obj" not in self.playlist[ctx.guild.id][0]:
                    return await self.clean_all(ctx, report=True)
                played_time = time.time() - self.playlist[ctx.guild.id][0]["time"]
                if played_time < 5:  # 再生時間が5秒以内だった場合
                    msg_obj = self.playlist[ctx.guild.id][0]["msg_obj"]
                    await msg_obj.delete()
                    await self.send_text(ctx, "SOMETHING_WENT_WRONG_WITH_TITLE", self.playlist[ctx.guild.id][0]["title"])
                if not self.status[ctx.guild.id]["auto"]:
                    if self.status[ctx.guild.id]["repeat"]:
                        pass
                    elif self.status[ctx.guild.id]["loop"]:
                        dt0 = self.playlist[ctx.guild.id].pop(0)
                        self.playlist[ctx.guild.id].append(dt0)
                    else:
                        self.playlist[ctx.guild.id].pop(0)
            if self.status[ctx.guild.id]["auto"]:
                await self.play_related_music(ctx)
            elif self.playlist[ctx.guild.id] != []:
                await self.play_right_away(ctx)
            else:
                self.status[ctx.guild.id]["status"] = 0
        except:
            await self.send_text(ctx, "UNKNOWN_ERROR")
            await self.report_error(ctx, "play_right_away", traceback2.format_exc())
            self.status[ctx.guild.id]["status"] = 0

    async def play_right_away(self, ctx):
        """
        プレイリストの次にある曲を再生
        :param ctx: Context
        :return:
        """
        try:
            # 処理中の場合
            if ctx.guild.id in self.status:
                if self.status[ctx.guild.id]["status"] != 3:
                    self.status[ctx.guild.id]["status"] = 3
            else:
                return await self.clean_all(ctx, report=True)
            async with ctx.typing():
                info = self.playlist[ctx.guild.id][0]
                try:
                    player = await YTDLSource.from_url(info["url"], loop=self.bot.loop, stream=True)
                except:
                    await self.send_text(ctx, "SOMETHING_WENT_WRONG_WHEN_LOADING_MUSIC")
                    await self.report_error(ctx, "play_right_away", traceback2.format_exc())
                    self.music_skiped.append(ctx.guild.id)
                    return await self.play_after(ctx)
                msg_obj = await self.send_text(ctx, "MUSIC_PLAY_NOW", info)
                try:
                    self.playlist[ctx.guild.id][0]["msg_obj"] = msg_obj
                    self.playlist[ctx.guild.id][0]["time"] = time.time()
                except:
                    return await self.clean_all(ctx, report=True)
                if ctx.voice_client is None:
                    return await self.clean_all(ctx, report=True)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_after(ctx),
                                                                                               self.bot.loop).result())
                ctx.voice_client.source.volume = self.status[ctx.guild.id]["volume"] / 100
                self.status[ctx.guild.id]["status"] = 1
        except:
            await self.send_text(ctx, "UNKNOWN_ERROR")
            await self.report_error(ctx, "play_right_away", traceback2.format_exc())
            self.status[ctx.guild.id]["status"] = 0

    async def play_related_music(self, ctx):
        """
        関連した曲を再生
        :param ctx: Context
        :return:
        """
        try:
            # 処理中の場合
            if ctx.guild.id in self.status:
                if self.status[ctx.guild.id]["status"] != 3:
                    self.status[ctx.guild.id]["status"] = 3
            else:
                return await self.clean_all(ctx, report=True)
            async with ctx.typing():
                dt0 = self.playlist[ctx.guild.id].pop(0)
                r = await self.get_request(
                    "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&relatedToVideoId={}&maxResults=10&key=".format(
                        dt0["id"]), ctx)
                res = {}
                if r[0] == 0:  # リクエスト処理中にエラーが発生
                    await self.send_text(ctx, "UNKNOWN_ERROR")
                    return await self.report_error(ctx, "play_related_music", "{}\n{}".format(r[1], pprint.pformat(r[2])))
                elif r[0] == 1:  # リクエスト成功 r[1]
                    res = r[1]
                    if len(res["items"]) == 0:
                        return await self.send_text(ctx, "NO_APPROPRIATE")
                index = random.randrange(len(res["items"]))
                res_d = await self.get_duration(res['items'][index]['id']['videoId'], ctx)
                if res_d[0] == 0: return
                info = {"url": "https://www.youtube.com/watch?v={}".format(res['items'][index]['id']['videoId']),
                        "title": res['items'][index]['snippet']['title'],
                        "id": res['items'][index]['id']['videoId'],
                        "thumbnail": res['items'][index]['snippet']['thumbnails']['high']['url'],
                        "publish": self.get_day(res['items'][index]['snippet']['publishedAt']),
                        "channel": res['items'][index]['snippet']['channelTitle'],
                        "user": ctx.author.display_name,
                        "duration": res_d[1]
                        }
                self.playlist[ctx.guild.id].append(info)
                try:
                    player = await YTDLSource.from_url(info["url"], loop=self.bot.loop, stream=True)
                except:
                    await self.send_text(ctx, "SOMETHING_WENT_WRONG_WHEN_LOADING_MUSIC")
                    await self.report_error(ctx, "play_related_music", traceback2.format_exc())
                    self.music_skiped.append(ctx.guild.id)
                    return await self.play_after(ctx)
                msg_obj = await self.send_text(ctx, "MUSIC_PLAY_NOW", info)
                try:
                    self.playlist[ctx.guild.id][0]["msg_obj"] = msg_obj
                    self.playlist[ctx.guild.id][0]["time"] = time.time()
                except:
                    return await self.clean_all(ctx, report=True)

                if ctx.voice_client is None:
                    return await self.clean_all(ctx, report=True)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_after(ctx),
                                                                                               self.bot.loop).result())
                ctx.voice_client.source.volume = self.status[ctx.guild.id]["volume"] / 100
                self.status[ctx.guild.id]["status"] = 1
        except:
            await self.send_text(ctx, "UNKNOWN_ERROR")
            await self.report_error(ctx, "play_after", traceback2.format_exc())
            self.status[ctx.guild.id]["status"] = 0

    async def get_duration(self, txt, ctx, playlist=False):
        """
        動画時間をAPIから取得
        :param txt: APIURL
        :param ctx: Context
        :param playlist: プレイリストかどうか
        :return: 整形後の動画時間
        """
        r = await self.get_request(
            "https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={}&key=".format(txt), ctx)
        if r[0] == 0:  # リクエスト処理中にエラーが発生
            await self.send_text(ctx, "UNKNOWN_ERROR")
            await self.report_error(ctx, "get_duration", "{}\n{}".format(r[1], pprint.pformat(r[2])))
            return [0]
        elif r[0] == 1:  # リクエスト成功 r[1]
            if playlist:
                return_list = []
                for i in range(len(r[1]['items'])):
                    return_list.append(self.return_duration(r[1]['items'][i]))
                return [1, return_list]
            else:
                return [1, self.return_duration(r[1]['items'][0])]

    async def get_index(self, ctx):
        """
        Searchの番号を取得
        :param ctx: Context
        :return:
        """
        ch = ctx.message.channel
        ah = ctx.message.author

        def check_index(m):
            return m.channel == ch and m.author == ah

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check_index)
        except asyncio.TimeoutError:
            await self.send_text(ctx, "PROCESS_TIMEOUT")
            return [0]
        if msg.content.isdigit():
            if 1 <= int(msg.content) <= 10:
                return [1, int(msg.content)]
            else:
                await self.send_text(ctx, "INVALID_NUMBER")
                return [0]
        else:
            await self.send_text(ctx, "INVALID_NUMBER")
            return [0]

    async def cog_before_invoke(self, ctx):
        """
        全コマンドの前に実行
        :param ctx: Context
        :return:
        """
        self.load_roles()
        if ctx.author.id in self.BAN:
            await self.send_text(ctx, "YOUR_ACCOUNT_BANNED")
            raise commands.CommandError("YOUR_ACCOUNT_BANNED")
        if ctx.author.voice is None:
            await self.send_text(ctx, "JOIN_VC_BEFORE_PLAY")
            raise commands.CommandError("JOIN_VC_BEFORE_PLAY")

    async def cog_command_error(self, ctx, error):
        """
        エラーが発生した時
        :param ctx: Context
        :param error: Error
        :return:
        """
        if isinstance(error, commands.MissingRequiredArgument):
            await self.send_text(ctx, "WRONG_COMMAND")
        elif isinstance(error, commands.errors.CommandNotFound):
            return
        elif isinstance(error, commands.errors.CommandError):
            return
        else:
            await self.send_text(ctx, "UNKNOWN_ERROR")
            await self.report_error(ctx, "on_command_error", str(error))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        ユーザーのボイスステータスが変更された時
        → 自動でボイスチャンネルを退出
        :param member: ユーザー
        :param before: 変更前のボイスステータス
        :param after: 変更後のボイスステータス
        :return:
        """
        if before.channel is not None:
            mem = before.channel.members
            if len(mem) == 1 and mem[0].id == self.bot.user.id:
                ctx = self.bot.get_channel(self.status[before.channel.guild.id]["channel"])
                await self.clean_all(ctx)
                await self.send_text(ctx, "DISCONNECTED_BECAUSE_ALL_USERS_LEFT")

    @commands.command(aliases=["j"])
    async def join(self, ctx):
        """
        ボイスチャンネルに接続
        :param ctx: Context
        :return:
        """
        try:
            code = await self.initialize_data(ctx)
        except:
            await ctx.send(traceback2.format_exc())
        if code == 1:  # 接続に成功した場合
            await self.send_text(ctx, "CONNECTED_TO_VC")
        elif code == 2:  # 移動した場合
            await self.send_text(ctx, "MOVED_VC")
        elif code == 3:  # 既に接続していた場合
            await self.send_text(ctx, "ALREADY_CONNECTED")
        elif code == 4:  # 処理拒否
            await self.send_text(ctx, "OPERATION_DENIED")

    @commands.command(aliases=['dc', 'dis'])
    async def disconnect(self, ctx):
        """
        VCから切断
        :param ctx: Context
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        else:
            return await self.clean_all(ctx, report=True)
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        else:
            await self.clean_all(ctx)
            await self.send_text(ctx, "DISCONNECTED_FROM_VC")

    @commands.command(aliases=['q', 'np', 'nowplaying'])
    async def queue(self, ctx):
        """
        キューを表示
        :param ctx: Context
        :return:
        """
        if ctx.guild.id not in self.playlist:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        if str(ctx.guild.region) == "japan":
            embed = discord.Embed(title="キュー", color=0xff22ff, url=self.info["WEB_URL_JA"])
        else:
            embed = discord.Embed(title="Queue", color=0xff22ff, url=self.info["WEB_URL"])
        count = 0
        if len(self.playlist[ctx.guild.id]) > 10:
            count = 10
        else:
            count = len(self.playlist[ctx.guild.id])
        chk = True
        if str(ctx.guild.region) == "japan":
            for i in range(count):
                if chk:
                    embed.add_field(name="再生中:", value="[{}]({}) | `{}` | `{}からのリクエスト`".format(
                        self.playlist[ctx.guild.id][i]["title"], self.playlist[ctx.guild.id][i]["url"],
                        self.playlist[ctx.guild.id][i]["duration"], self.playlist[ctx.guild.id][i]["user"]),
                                    inline=False)
                else:
                    embed.add_field(name=str(i) + ":", value="[{}]({}) | `{}` | `{}からのリクエスト`".format(
                        self.playlist[ctx.guild.id][i]["title"], self.playlist[ctx.guild.id][i]["url"],
                        self.playlist[ctx.guild.id][i]["duration"], self.playlist[ctx.guild.id][i]["user"]),
                                    inline=False)
                chk = False
        else:
            for i in range(count):
                if chk:
                    embed.add_field(name="Now Playing:", value="[{}]({}) | `{}` | `Requested by {}`".format(
                        self.playlist[ctx.guild.id][i]["title"], self.playlist[ctx.guild.id][i]["url"],
                        self.playlist[ctx.guild.id][i]["duration"], self.playlist[ctx.guild.id][i]["user"]),
                                    inline=False)
                else:
                    embed.add_field(name=str(i) + ":", value="[{}]({}) | `{}` | `Requested by {}`".format(
                        self.playlist[ctx.guild.id][i]["title"], self.playlist[ctx.guild.id][i]["url"],
                        self.playlist[ctx.guild.id][i]["duration"], self.playlist[ctx.guild.id][i]["user"]),
                                    inline=False)
                chk = False
        modes = ""
        if self.status[ctx.guild.id]["auto"]:
            modes += "auto: `on` | "
        else:
            modes += "auto: `off` | "
        if self.status[ctx.guild.id]["loop"]:
            modes += "loop: `on` | "
        else:
            modes += "loop: `off` | "
        if self.status[ctx.guild.id]["repeat"]:
            modes += "repeat: `on`"
        else:
            modes += "repeat: `off`"
        if str(ctx.guild.region) == "japan":
            embed.add_field(name="モード:", value=modes, inline=False)
            embed.add_field(name="合計:", value="{}曲.".format(str(len(self.playlist[ctx.guild.id]))), inline=False)
        else:
            embed.add_field(name="Modes:", value=modes, inline=False)
            embed.add_field(name="Total:", value="{} songs in queue.".format(str(len(self.playlist[ctx.guild.id]))),
                            inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["p"])
    async def play(self, ctx, *, url):
        """
        音楽を再生
        :param ctx: Context
        :param url: 曲名,URL等
        :return:
        """
        try:
            # 初期化
            code = await self.initialize_data(ctx)
            if code == 0:  # VC接続に失敗した場合
                return
            elif code == 4:  # 操作拒否
                return await self.send_text(ctx, "OPERATION_DENIED")
            if self.status[ctx.guild.id]["auto"]:
                return await self.send_text(ctx, "AUTO_MODE_ON")
            user = ctx.author.display_name
            # url解析
            url_code = self.check_url(url)
            if url_code[0] == 0:
                if url_code[1] == 0:
                    return await self.send_text(ctx, "WRONG_URL")
                elif url_code[1] == 1:
                    return await self.send_text(ctx, "NOT_SUPPORTED")
            elif url_code[0] == 1:
                r = await self.get_request(
                    "https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={}&maxResults=1&type=video&key=".format(
                        url_code[1]), ctx)
                if r[0] == 0:  # リクエスト処理中にエラーが発生
                    await self.send_text(ctx, "UNKNOWN_ERROR")
                    return await self.report_error(ctx, "play", "{}\n{}".format(r[1], pprint.pformat(r[2])))
                elif r[0] == 1:  # リクエスト成功 r[1]
                    res = r[1]
                    if len(res["items"]) == 0:
                        return await self.send_text(ctx, "NO_APPROPRIATE")
                    info = {
                        "url": "https://www.youtube.com/watch?v={}".format(res['items'][0]['id']),
                        "title": res['items'][0]['snippet']['title'],
                        "id": res['items'][0]['id'],
                        "thumbnail": res['items'][0]['snippet']['thumbnails']['high']['url'],
                        "publish": self.get_day(res['items'][0]['snippet']['publishedAt']),
                        "channel": res['items'][0]['snippet']['channelTitle'],
                        "user": user,
                        "duration": self.return_duration(res['items'][0])
                    }
                    self.playlist[ctx.guild.id].append(info)
                    await self.send_text(ctx, "MUSIC_ADDED", info)
            elif url_code[0] == 2:
                r = await self.get_request(
                    "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={}&maxResults=50&key=".format(
                        url_code[1]), ctx)
                if r[0] == 0:  # リクエスト処理中にエラーが発生
                    await self.send_text(ctx, "UNKNOWN_ERROR")
                    return await self.report_error(ctx, "play", "{}\n{}".format(r[1], pprint.pformat(r[2])))
                elif r[0] == 1:  # リクエスト成功 r[1]
                    res = r[1]
                    if len(res["items"]) == 0:
                        return await self.send_text(ctx, "WRONG_URL")
                    id_list = ""
                    for i in range(len(res["items"])):
                        try:
                            id_list += "{},".format(res['items'][i]['snippet']['resourceId']['videoId'])
                        except KeyError:
                            pass
                    res_d = await self.get_duration(id_list[:-1], ctx, playlist=True)
                    if res_d[0] == 0: return
                    for i in range(len(res["items"])):
                        try:
                            info = {"url": "https://www.youtube.com/watch?v={}".format(
                                res['items'][i]['snippet']['resourceId']['videoId']),
                                    "title": res['items'][i]['snippet']['title'],
                                    "id": res['items'][i]['snippet']['resourceId']['videoId'],
                                    "thumbnail": res['items'][i]['snippet']['thumbnails']['high']['url'],
                                    "publish": self.get_day(res['items'][i]['snippet']['publishedAt']),
                                    "channel": res['items'][i]['snippet']['channelTitle'],
                                    "user": user,
                                    "duration": res_d[1][i]
                                    }
                            self.playlist[ctx.guild.id].append(info)
                        except KeyError:
                            pass
                        except IndexError:
                            break
                    await self.send_text(ctx, "PLAYLIST_ADDED", info, len(res["items"]))
            elif url_code[0] == 3:
                r = await self.get_request(
                    "https://www.googleapis.com/youtube/v3/search?part=snippet&q={}&maxResults=1&type=video&key=".format(
                        url_code[1]), ctx)
                if r[0] == 0:  # リクエスト処理中にエラーが発生
                    await self.send_text(ctx, "UNKNOWN_ERROR")
                    return await self.report_error(ctx, "play", "{}\n{}".format(r[1], pprint.pformat(r[2])))
                elif r[0] == 1:  # リクエスト成功 r[1]
                    res = r[1]
                    if len(res["items"]) == 0:
                        return await self.send_text(ctx, "NO_APPROPRIATE")
                    res_d = await self.get_duration(res['items'][0]['id']['videoId'], ctx)
                    if res_d[0] == 0: return
                    info = {
                        "url": "https://www.youtube.com/watch?v={}".format(res['items'][0]['id']['videoId']),
                        "title": res['items'][0]['snippet']['title'],
                        "id": res['items'][0]['id']['videoId'],
                        "thumbnail": res['items'][0]['snippet']['thumbnails']['high']['url'],
                        "publish": self.get_day(res['items'][0]['snippet']['publishedAt']),
                        "channel": res['items'][0]['snippet']['channelTitle'],
                        "user": user,
                        "duration": res_d[1]
                    }
                    self.playlist[ctx.guild.id].append(info)
                    await self.send_text(ctx, "MUSIC_ADDED", info)
            # 再生
            # if (not ctx.voice_client.is_playing()) and (not ctx.voice_client.is_paused()):
            if self.status[ctx.guild.id]["status"] == 0:
                await self.play_right_away(ctx)

        except:
            await ctx.send(traceback2.format_exc())

    @commands.command(aliases=["se"])
    async def search(self, ctx, *, url):
        """
        曲を検索
        :param ctx: Context
        :param url: 曲名
        :return:
        """
        code = await self.initialize_data(ctx)
        if code == 0:  # VC接続に失敗した場合
            return
        elif code == 4:  # 操作拒否
            return await self.send_text(ctx, "OPERATION_DENIED")
        if self.status[ctx.guild.id]["auto"]:
            return await self.send_text(ctx, "AUTO_MODE_ON")
        r = await self.get_request(
            "https://www.googleapis.com/youtube/v3/search?part=snippet&q={}&maxResults=10&type=video&key=".format(url),
            ctx)
        res = {}
        if r[0] == 0:  # リクエスト処理中にエラーが発生
            await self.send_text(ctx, "UNKNOWN_ERROR")
            return await self.report_error(ctx, "search", "{}\n{}".format(r[1], pprint.pformat(r[2])))
        elif r[0] == 1:  # リクエスト成功 r[1]
            res = r[1]
            if len(res["items"]) == 0:
                return await self.send_text(ctx, "NO_APPROPRIATE")
        embed = discord.Embed(title="Search", color=0xaaaaaa)
        for i in range(1, len(res["items"]) + 1):
            embed.add_field(name=str(i) + ":", value="{}".format(res['items'][i - 1]['snippet']['title'], ),
                            inline=False)
        if str(ctx.guild.region) == "japan":
            embed.add_field(name="＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿", value="番号を入力して曲を指定します.\n一定時間経過するとタイムアウトします.", inline=False)
        else:
            embed.add_field(name="＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿",
                            value="Type number to select music.\nIt will time out after a certain period of time",
                            inline=False)
        await ctx.send(embed=embed)
        user = ctx.message.author.display_name;
        ix = 0
        rx = await self.get_index(ctx)
        if rx[0] == 0:
            return
        elif rx[0] == 1:
            ix = rx[1]
        res_d = await self.get_duration(res['items'][ix - 1]['id']['videoId'], ctx)
        if res_d[0] == 0: return
        info = {"url": "https://www.youtube.com/watch?v={}".format(res['items'][ix - 1]['id']['videoId']),
                "title": res['items'][ix - 1]['snippet']['title'],
                "id": res['items'][ix - 1]['id']['videoId'],
                "thumbnail": res['items'][ix - 1]['snippet']['thumbnails']['high']['url'],
                "publish": self.get_day(res['items'][ix - 1]['snippet']['publishedAt']),
                "channel": res['items'][ix - 1]['snippet']['channelTitle'],
                "user": user,
                "duration": res_d[1]
                }
        self.playlist[ctx.guild.id].append(info)
        await self.send_text(ctx, "MUSIC_ADDED", info)
        # if (not ctx.voice_client.is_playing()) and (not ctx.voice_client.is_paused()):
        if self.status[ctx.guild.id]["status"] == 0:
            await self.play_right_away(ctx)

    @commands.command(aliases=["a"])
    async def auto(self, ctx, *, url):
        """
        自動再生モードで曲を再生
        :param ctx: Context
        :param url: 曲名
        :return:
        """
        code = await self.initialize_data(ctx)
        if code == 0:  # VC接続に失敗した場合
            return
        elif code == 4:  # 操作拒否
            return await self.send_text(ctx, "OPERATION_DENIED")
        if url == "off":
            if not self.status[ctx.guild.id]["auto"]:
                await self.send_text(ctx, "AUTO_ALREADY_OFF")
            else:
                self.status[ctx.guild.id]["auto"] = False
                await self.send_text(ctx, "AUTO_OFF")
            return
        user = ctx.author.display_name
        r = await self.get_request(
            "https://www.googleapis.com/youtube/v3/search?part=snippet&q={}&maxResults=1&type=video&key=".format(url),
            ctx)
        res = {}
        if r[0] == 0:
            await self.send_text(ctx, "UNKNOWN_ERROR")
            return await self.report_error(ctx, "auto", "{}\n{}".format(r[1], pprint.pformat(r[2])))
        elif r[0] == 1:
            res = r[1]
            if len(res["items"]) == 0:
                return await self.send_text(ctx, "NO_APPROPRIATE")
        self.status[ctx.guild.id]["auto"] = True
        self.playlist[ctx.guild.id] = []
        self.status[ctx.guild.id]["loop"] = False
        self.status[ctx.guild.id]["repeat"] = False
        self.disconnected.append(ctx.guild.id)
        if ctx.voice_client.source is not None:
            ctx.voice_client.source.cleanup()
        if ctx.guild.id in self.disconnected:
            self.disconnected.remove(ctx.guild.id)
        await self.send_text(ctx, "AUTO_ENABLED", url)
        res_d = await self.get_duration(res['items'][0]['id']['videoId'], ctx)
        if res_d[0] == 0: return
        info = {"url": "https://www.youtube.com/watch?v={}".format(res['items'][0]['id']['videoId']),
                "title": res['items'][0]['snippet']['title'],
                "id": res['items'][0]['id']['videoId'],
                "thumbnail": res['items'][0]['snippet']['thumbnails']['high']['url'],
                "publish": self.get_day(res['items'][0]['snippet']['publishedAt']),
                "channel": res['items'][0]['snippet']['channelTitle'],
                "user": user,
                "duration": res_d[1]
                }
        self.playlist[ctx.guild.id].append(info)
        # if (not ctx.voice_client.is_playing()) and (not ctx.voice_client.is_paused()):
        if self.status[ctx.guild.id]["status"] == 0:
            await self.play_right_away(ctx)

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        """
        曲をスキップ
        :param ctx: Context
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        else:
            return await self.clean_all(ctx, report=True)
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        # elif (not ctx.voice_client.is_playing()) and (ctx.voice_client.is_paused()):
        elif self.status[ctx.guild.id]["status"] == 0:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        else:
            self.music_skiped.append(ctx.guild.id)
            if ctx.voice_client.source is not None:
                ctx.voice_client.source.cleanup()
            else:
                await self.play_after(ctx)
            await self.send_text(ctx, "SKIPPED")

    @commands.command(aliases=['ps'])
    async def pause(self, ctx):
        """
        曲を停止
        :param ctx: Context
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        else:
            return await self.clean_all(ctx, report=True)
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.status[ctx.guild.id]["status"] == 0:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        # elif ctx.voice_client.is_paused():
        elif self.status[ctx.guild.id]["status"] == 2:
            await self.send_text(ctx, "ALREADY_PAUSED")
        # elif ctx.voice_client.is_playing():
        elif self.status[ctx.guild.id]["status"] == 1:
            ctx.voice_client.pause()
            self.status[ctx.guild.id]["status"] = 2
            await self.send_text(ctx, "PAUSED_MUSIC")
        else:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
            await self.report_error(ctx, "pause", "どの例にも当てはまらない状況が発生しました.\nstatus:{}".format(self.status[ctx.guild.id]["status"]))

    @commands.command(aliases=['re', 'res'])
    async def resume(self, ctx):
        """
        曲を再開
        :param ctx: Context
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        else:
            return await self.clean_all(ctx, report=True)
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.status[ctx.guild.id]["status"] == 0:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        # elif ctx.voice_client.is_playing():
        elif self.status[ctx.guild.id]["status"] == 1:
            await self.send_text(ctx, "ALREADY_RESUMED")
        # elif ctx.voice_client.is_paused():
        elif self.status[ctx.guild.id]["status"] == 2:
            ctx.voice_client.resume()
            self.status[ctx.guild.id]["status"] = 1
            await self.send_text(ctx, "RESUMED_MUSIC")
        else:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")

    @commands.command(aliases=['l'])
    async def loop(self, ctx):
        """
        ループモードで設定
        :param ctx:
        :return:
        """
        if self.status[ctx.guild.id]["auto"]:
            return await self.send_text(ctx, "AUTO_MODE_ON")
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif ctx.guild.id not in self.status:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.status[ctx.guild.id]['loop']:
            self.status[ctx.guild.id]['loop'] = False
            await self.send_text(ctx, "LOOP_OFF")
        elif not self.status[ctx.guild.id]['loop']:
            self.status[ctx.guild.id]['loop'] = True
            await self.send_text(ctx, "LOOP_ON")

    @commands.command(aliases=['rep'])
    async def repeat(self, ctx):
        """
        リピートモードを設定
        :param ctx: Context
        :return:
        """
        if self.status[ctx.guild.id]["auto"]:
            return await self.send_text(ctx, "AUTO_MODE_ON")
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif ctx.guild.id not in self.status:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.status[ctx.guild.id]['repeat']:
            self.status[ctx.guild.id]['repeat'] = False
            await self.send_text(ctx, "REPEAT_OFF")
        elif not self.status[ctx.guild.id]['repeat']:
            self.status[ctx.guild.id]['repeat'] = True
            await self.send_text(ctx, "REPEAT_ON")

    @commands.command(aliases=['v'])
    async def volume(self, ctx, volume: int):
        """
        音量を変更
        :param ctx: Context
        :param volume: 音量
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        else:
            return await self.clean_all(ctx, report=True)
        if ctx.voice_client is None:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.status[ctx.guild.id]["status"] == 0:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        # if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        elif self.status[ctx.guild.id]["status"] == 1 or self.status[ctx.guild.id]["status"] == 2:
            ctx.voice_client.source.volume = volume / 100
            self.status[ctx.guild.id]["volume"] = volume
            await self.send_text(ctx, "VOLUME_CHANGED", volume)

    @commands.command(aliases=['rm'])
    async def remove(self, ctx, index: int):
        """
        曲を削除
        :param ctx: Context
        :param index: 曲の番号
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        if self.status[ctx.guild.id]["auto"]:
            return await self.send_text(ctx, "AUTO_MODE_ON")
        if ctx.guild.id not in self.playlist:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.playlist[ctx.guild.id] == []:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif index == 0:
            return await self.send_text(ctx, "YOU_CANT_REMOVE_CURRENTLY_MUSIC")
        elif index < 0:
            return await self.send_text(ctx, "VALUE_LESS_THAN_0")
        elif (len(self.playlist[ctx.guild.id]) - 1) < index:
            return await self.send_text((ctx, "WRONG_INDEX"))
        else:
            info = self.playlist[ctx.guild.id].pop(index)
            await self.send_text(ctx, "MUSIC_REMOVED", info)

    @commands.command(aliases=['cl'])
    async def clear(self, ctx):
        """
        曲をクリア
        :param ctx: Context
        :return:
        """
        # 処理中の場合
        if ctx.guild.id in self.status:
            if self.status[ctx.guild.id]["status"] == 3:
                return await self.send_text(ctx, "OPERATION_DENIED")
        else:
            return await self.clean_all(ctx, report=True)
        if self.status[ctx.guild.id]["auto"]:
            return await self.send_text(ctx, "AUTO_MODE_ON")
        if ctx.guild.id not in self.playlist:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        elif self.playlist[ctx.guild.id] == []:
            await self.send_text(ctx, "NOT_PLAYING_MUSIC")
        else:
            save = self.playlist[ctx.guild.id][0]
            self.playlist[ctx.guild.id].clear()
            self.playlist[ctx.guild.id].append(save)
            await self.send_text(ctx, "CLEARED_MUSIC")


def setup(bot):
    bot.add_cog(Music(bot))
