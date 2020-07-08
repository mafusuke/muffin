# import
from discord.ext import commands, tasks
import asyncio, discord, io, json, os, random, sys, time, traceback2


class Game(commands.Cog):

    def __init__(self, bot):
        self.bot = bot  # type: commands.Bot
        with open("./INFO.json") as F:
            info = json.load(F)
        self.info = info
        with open("./DATABASE.json") as F:
            database = json.load(F)
        self.bot.database = database
        with open("./correct.json") as F:
            correct = json.load(F)
        self.correct = correct

    def save_database(self):
        with open("./DATABASE.json", 'w') as F:
            json.dump(self.bot.database, F, indent=2)

    def initialize_data(self, user_id):
        self.bot.database[str(user_id)] = {
            "best_score": 30,
            "single": {
                "all_matches": 0,
                "win_matches": 0
            },
            "multi": {
                "all_matches": 0,
                "win_matches": 0
            }
        }

    async def send_text(self, ctx, code, arg1=None, arg2=None):
        if code == "YOUR_ACCOUNT_BANNED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`あなたはBANされているため,使用できません.\n異議申し立ては公式サーバーにてお願いします.`")
                raise commands.CommandError("Your Account Banned")
            else:
                await ctx.send(
                    ":warning:`You cannnot use because you are banned.\nFor objection please use Official Server.`")
                raise commands.CommandError("Your Account Banned")
        elif code == "WRONG_COMMAND_SC":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f":warning:コマンドが間違っています.正しい構文: `{self.bot.PREFIX}play [人数] [試合数]`")
            else:
                await ctx.send(f":warning:Command is wrong. Correct syntax: `{self.bot.PREFIX}play [number of players] [number of matches]`")
        elif code == "WRONG_COMMAND":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`コマンドが間違っています.構文が正しいことを確認してください!`")
            else:
                await ctx.send(":warning:`Wrong command.Please check your arguments are valid!`")
        elif code == "UNKNOWN_ERROR":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:`不明なエラーが発生しました.`")
            else:
                await ctx.send(":warning:`Unknown error has occurred.`")
        elif code == "SPECIFY_AS_INTEGER":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:整数で指定してください.")
            else:
                await ctx.send(":warning:Please specify as an integer.")
        elif code == "SPECIFY_WITH_1_OR_MORE":
            if str(ctx.guild.region) == "japan":
                await ctx.send(":warning:1以上で指定してください.")
            else:
                await ctx.send(":warning:Please specify with ️1 or more.")
        elif code == "CORRECT_ANSWER_SINGLE":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCmaru']}あなたは正解しました!")
            else:
                await ctx.send(f"{self.info['SCmaru']} You got correct answer!")
        elif code == "INCORRECT_ANSWER_SINGLE":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCbatu']}あなたは間違いました!")
            else:
                await ctx.send(f"{self.info['SCbatu']} You got incorrect answer!")
        elif code == "BEST_SCORE":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCcongr']} <@{arg1}>さん!ベストスコア更新!\nあなたのスコア:{arg2}[s]")
            else:
                await ctx.send(f"{self.info['SCcongr']} <@{arg1}>! Your best score updated!\nScore:{arg2}[s]")
        elif code == "NO_ONE_RESPOND":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']}回答できた人がいなかったため,この問題を終了します.")
            else:
                await ctx.send(f"{self.info['SCwarning']} This question ends because no one could answer.")
        elif code == "MATCH_TIMEOUT":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']} 2回連続で回答がなかったためこの部屋を終了します.")
            else:
                await ctx.send(f"{self.info['SCwarning']} This room will be closed because there was no response twice in a row.")
        elif code == "ON_JOIN":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}>さんが参加しました.")
            else:
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}> joined.")
        elif code == "ALREADY_JOIN":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}>さんは既に参加しています.")
            else:
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}> already joined.")
        elif code == "ON_CANCEL":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCbatu']}<@{arg1}>さんの参加をキャンセルしました.")
            else:
                await ctx.send(f"{self.info['SCbatu']}<@{arg1}> canceled.")
        elif code == "NOT_JOINED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}>さんは参加していません.")
            else:
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}> didn't join.")
        elif code == "VOTE_GO":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}>さんが強制的にスタートに投票しました.({arg2}/2)")
            else:
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}> voted for forcibly start. ({arg2}/2)")
        elif code == "FORCE_START":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCcheck']} 2人が強制的にスタートに投票したため{arg1}人モードに変更します.")
            else:
                await ctx.send(f"{self.info['SCcheck']} Change to {arg1} person mode because 2 people vote for force start.")
        elif code == "ALREADY_VOTED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}>さんは既に強制的にスタートに投票しています.({arg2}/2)")
            else:
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}> already voted for force start.({arg2}/2)")
        elif code == "NOT_JOINED_VOTE":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}>さんは参加していないので投票できません!")
            else:
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}> can't vote because not joined match.")
        elif code == "SESSION_ENDED":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']} 一定時間反応がなかったためセッションを終了しました.")
            else:
                await ctx.send(f"{self.info['SCwarning']} The session ended because there was no response for a certain period of time.")
        elif code == "START_MATCH":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCcheck']} 定員に達したためゲームを開始します!")
            else:
                await ctx.send(f"{self.info['SCcheck']} The game has started because the number of people has reached the limit!")
        elif code == "CORRECT_ANSWER":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}>さん!あなたは正解しました!")
            else:
                await ctx.send(f"{self.info['SCmaru']}<@{arg1}> You got correct answer!")
        elif code == "INCORRECT_ANSWER":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCbatu']}<@{arg1}>さん!あなたは間違いました!\nこの試合であなたはこれ以上回答できません!\n次のラウンドをお待ちください.")
            else:
                await ctx.send(f"{self.info['SCbatu']}<@{arg1}> You got incorrect answer!\nYou can't answer any more in this match!\nPlease wait for the next round.")
        elif code == "ALREADY_INCORRECT":
            if str(ctx.guild.region) == "japan":
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}>さん!あなたはすでに間違っているためこれ以上回答できません!\n次のラウンドをお待ちください.")
            else:
                await ctx.send(f"{self.info['SCwarning']}<@{arg1}> You can't answer anymore because you are already wrong!\nPlease wait for the next round.")

    async def report_error(self, ctx, name, message):
        """
        エラーをログチャンネルに送信
        :param ctx: Context
        :param name: 関数名
        :param message: エラーメッセージ
        :return:
        """
        channel = self.bot.get_channel(self.info["ERROR_CHANNEL"])
        try:
            embed = discord.Embed(title=name, description=message)
            embed.set_author(name="Error Reporter")
            await channel.send(embed=embed)
        except:
            embed = discord.Embed(title=name, description="<TOO LONG>")
            embed.set_author(name="Error Reporter")
            msg = await channel.send(embed=embed, file=discord.File(fp=io.StringIO(message), filename="error.txt"))

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

    async def cog_before_invoke(self, ctx):
        if ctx.author.id in self.bot.BAN:
            await self.send_text(ctx, "YOUR_ACCOUNT_BANNED")
            raise commands.CommandError("Your Account Banned")

    @commands.command(aliases=["r"])
    async def rule(self, ctx):
        if str(ctx.guild.region) == "japan":
            embed = discord.Embed(title="Rule Of Shadow Choice (1/3)")
            embed.set_image(url=f"{self.info['PICT_URL']}Tehon.jpg")
            embed.add_field(name="基本",
                            value="```これらは重要な5つのアイテムです.\n今から説明する2つのルールにあったアイテムをこの中から選ぶことになります.\nこれらは問題の下部にリアクションとして表示されます.\nまた各問題の右上にも表示されるので適宜参照してください.\n(注意)色鉛筆は2色を持ちます.オレンジ色と黄色は同じ1つの色(黄色)とみなします.\nではその二つのルールを説明します!```")
        await ctx.send(embed=embed)
        embed = discord.Embed(title="Rule Of Shadow Choice (2/3)")
        embed.set_image(url=f"{self.info['PICT_URL']}Tehon.jpg")
        embed.set_image(url=f"{self.info['PICT_URL']}/main/1.jpg")
        embed.add_field(name="ルール1",
                        value="```表示された絵の中に上で示した５つのうちのどれかが同じ色で入っている場合それが正解です!\nすかさずそのアイテムのリアクションをおしましょう.```",
                        inline=False)
        embed.add_field(name="例1", value="```この場合絵の中に名刺が同じ色(紫)でうつっているので紫の名刺のリアクションが正解です.```", inline=False)
        await ctx.send(embed=embed)
        embed = discord.Embed(title="Rule Of Shadow Choice (3/3)")
        embed.set_image(url=f"{self.info['PICT_URL']}Tehon.jpg")
        embed.set_image(url=f"{self.info['PICT_URL']}/main/11.jpg")
        embed.add_field(name="ルール2", value="```カードの中に正しい色で写っているモノがなければ(ルール1を満たすものがなければ)、\n色も種類も絵に映っていないアイテムをとりましょう.```",
                        inline=False)
        embed.add_field(name="例2",
                        value="```この場合絵の中に正しい色でうつっているものはないので,色も種類も絵に写っていないものを探します.\nはさみ,緑,黄,えんぴつがだめなので,'黄'のノート,赤い'はさみ','緑'のメジャー,青の'鉛筆'はダメです.\nよって残った紫のメジャーが正解です.```",
                        inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["st"])
    async def status(self, ctx):
        if ctx.message.mentions == []:
            embed = discord.Embed(title="ステータス")
            embed.set_thumbnail(url=ctx.author.avatar_url)
            decoration = ""
            if ctx.author.id in self.bot.ADMIN:
                embed.add_field(name="ユーザーー情報", value=f"```yaml\nユーザー:{ctx.author}\nユーザーID:{ctx.author.id}\n[管理者]```", inline=False)
            elif ctx.author.id in self.bot.Contributor:
                embed.add_field(name="ユーザーー情報", value=f"```fix\nユーザー:{ctx.author}\nユーザーID:{ctx.author.id}\n[貢献者]```", inline=False)
            else:
                embed.add_field(name="ユーザーー情報", value=f"```ユーザー:{ctx.author}\nユーザーID:{ctx.author.id}```", inline=False)
            if str(ctx.author.id) in self.bot.database:
                embed.add_field(name="ShadowChoice",
                                value="```c\n最短正答時間:{}\nシングルスコア:\n  全試合数:{}\n  勝利試合数:{}\n  勝率:{}%\nマルチスコア:\n  全試合数:{}\n  勝利試合数:{}\n  勝率:{}%```".format(
                                    self.bot.database[str(ctx.author.id)]["best_score"],
                                    self.bot.database[str(ctx.author.id)]["single"]["all_matches"],
                                    self.bot.database[str(ctx.author.id)]["single"]["win_matches"],
                                    round(
                                        self.bot.database[str(ctx.author.id)]["single"]["win_matches"] /
                                        self.bot.database[str(ctx.author.id)]["single"]["all_matches"] * 100, 2
                                    ),
                                    self.bot.database[str(ctx.author.id)]["multi"]["all_matches"],
                                    self.bot.database[str(ctx.author.id)]["multi"]["win_matches"],
                                    round(
                                        self.bot.database[str(ctx.author.id)]["multi"]["win_matches"] /
                                        self.bot.database[str(ctx.author.id)]["multi"]["all_matches"] * 100, 2
                                    )))
            else:
                embed.add_field(name="ShadowChoice", value="```まだプレイしていません.```")
            await ctx.send(embed=embed)
        else:
            target = ctx.message.mentions[0]
            embed = discord.Embed(title="ステータス")
            embed.set_thumbnail(url=target.avatar_url)
            if target.id in self.bot.ADMIN:
                embed.add_field(name="ユーザーー情報", value=f"```yaml\nユーザー:{target}\nユーザーID:{target.id}\n[管理者]```", inline=False)
            elif target.id in self.bot.Contributor:
                embed.add_field(name="ユーザーー情報", value=f"```fix\nユーザー:{target}\nユーザーID:{target.id}\n[貢献者]```", inline=False)
            else:
                embed.add_field(name="ユーザーー情報", value=f"```ユーザー:{target}\nユーザーID:{target.id}```", inline=False)
            if str(target.id) in self.bot.database:
                embed.add_field(name="ShadowChoice",
                                value="```c\n最短正答時間:{}\nシングルスコア:\n  全試合数:{}\n  勝利試合数:{}\n  勝率:{}%\nマルチスコア:\n  全試合数:{}\n  勝利試合数:{}\n  勝率:{}%```".format(
                                    self.bot.database[str(target.id)]["best_score"],
                                    self.bot.database[str(target.id)]["single"]["all_matches"],
                                    self.bot.database[str(target.id)]["single"]["win_matches"], round(
                                        self.bot.database[str(target.id)]["single"]["win_matches"] /
                                        self.bot.database[str(target.id)]["single"]["all_matches"] * 100, 2),
                                    self.bot.database[str(target.id)]["multi"]["all_matches"],
                                    self.bot.database[str(target.id)]["multi"]["win_matches"], round(
                                        self.bot.database[str(target.id)]["multi"]["win_matches"] /
                                        self.bot.database[str(target.id)]["multi"]["all_matches"] * 100, 2)))
            else:
                embed.add_field(name="ShadowChoice", value="```まだプレイしていません.```")
            await ctx.send(embed=embed)

    @commands.command(aliases=["sc"])
    async def shadowchoice(self, ctx):
        try:
            msg_list = ctx.message.content.split()
            mode: int
            afk = 0
            is_right: int
            if len(msg_list) == 1:
                mode = 1
                round_time = 1
            elif len(msg_list) > 3:
                return await self.send_text(ctx, "WRONG_COMMAND_SC")
            elif len(msg_list) == 2:
                if not msg_list[1].isdigit():
                    return await self.send_text(ctx, "SPECIFY_AS_INTEGER")
                elif int(msg_list[1]) < 1:
                    return await self.send_text(ctx, "SPECIFY_WITH_1_OR_MORE")
                else:
                    mode = int(msg_list[1])
                    round_time = 1
            else:
                if (not msg_list[1].isdigit()) or (not msg_list[2].isdigit()):
                    return await self.send_text(ctx, "SPECIFY_AS_INTEGER")
                elif (int(msg_list[1]) < 1) or (int(msg_list[2]) < 1):
                    return await self.send_text(ctx, "SPECIFY_WITH_1_OR_MORE")
                else:
                    mode = int(msg_list[1])
                    round_time = int(msg_list[2])
            if mode == 1:
                if str(ctx.author.id) not in self.bot.database:
                    self.initialize_data(ctx.author.id)
                for i in range(round_time):
                    if str(ctx.guild.region) == "japan":
                        embed = discord.Embed(title="約5秒お待ちください...")
                        embed.add_field(name="お待ちください", value="`約5秒後に開始されます!`")
                    else:
                        embed = discord.Embed(title="Please wait about 5 seconds...")
                        embed.add_field(name="Please wait", value="`It will start in about 5 seconds!`")
                    org_msg = await ctx.send(embed=embed)
                    await org_msg.add_reaction(self.info["SCnotebook"])
                    await org_msg.add_reaction(self.info["SCmajor"])
                    await org_msg.add_reaction(self.info["SCscissors"])
                    await org_msg.add_reaction(self.info["SCCard"])
                    await org_msg.add_reaction(self.info["SCPencil"])
                    ch = ctx.message.channel
                    ah = ctx.message.author
                    num = str(random.randint(1, 25))
                    num_id = self.correct[num]
                    def check(r, u):
                        return u == ah and r.message.channel == ch and r.message.id == org_msg.id and r.emoji.id in \
                               self.info["SC"]
                    embed = discord.Embed(title=f"Question of Shadow Choice ({i+1}/{round_time})")
                    embed.set_thumbnail(url=f"{self.info['PICT_URL']}Tehon.jpg")
                    embed.set_image(url=f"{self.info['PICT_URL']}/main/{num}.jpg")
                    if str(ctx.guild.region) == "japan":
                        embed.add_field(name="問題", value="下のリアクションを押して回答してください!")
                    else:
                        embed.add_field(name="Question", value="Please press the reaction below to answer!")
                    await org_msg.edit(embed=embed)
                    pstart = time.time()
                    try:
                        preaction, puser = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                        elapsed_time = time.time() - pstart
                        if preaction.emoji.id == num_id:
                            await self.send_text(ctx, "CORRECT_ANSWER_SINGLE")
                            is_right = 1
                        else:
                            await self.send_text(ctx, "INCORRECT_ANSWER_SINGLE")
                            is_right = 0
                        elapsed_time = round(elapsed_time, 2)
                        embed = discord.Embed(title=f"Question of Shadow Choice ({i+1}/{round_time})")
                        if str(ctx.guild.region) == "japan":
                            embed.add_field(name="終了済", value="試合はすでに終了しています.")
                        else:
                            embed.add_field(name="Ended", value="The match has already ended.")
                        await org_msg.edit(embed=embed)
                        if is_right == 1:
                            embed = discord.Embed(title=f"Result of Shadow Choice ({i+1}/{round_time})")
                            if str(ctx.guild.region) == "japan":
                                embed.add_field(name="結果発表", value=f"```正解者:{puser.display_name}\n計測時間:{elapsed_time}[s]```")
                            else:
                                embed.add_field(name="Result", value=f"```Winner:{puser.display_name}\nTime:{elapsed_time}[s]```")
                            await ctx.send(embed=embed)
                            if self.bot.database[str(puser.id)]["best_score"] > elapsed_time:
                                self.bot.database[str(puser.id)]["best_score"] = elapsed_time
                                await self.send_text(ctx, "BEST_SCORE", arg1=puser.id, arg2=elapsed_time)
                            self.bot.database[str(puser.id)]["single"]["win_matches"] += 1
                        else:
                            embed = discord.Embed(title=f"Result of Shadow Choice ({i+1}/{round_time})")
                            if str(ctx.guild.region) == "japan":
                                embed.add_field(name="結果発表", value=f"```正解者:なし\n計測時間:{elapsed_time}[s]```")
                            else:
                                embed.add_field(name="Result", value=f"```Winner: None\nTime:{elapsed_time}[s]```")
                            await ctx.send(embed=embed)
                        self.bot.database[str(puser.id)]["single"]["all_matches"] += 1
                        self.save_database()
                        afk = 0
                    except asyncio.TimeoutError:
                        elapsed_time = time.time() - pstart
                        elapsed_time = round(elapsed_time, 2)
                        await self.send_text(ctx, "NO_ONE_RESPOND")
                        embed = discord.Embed(title="Result of Shadow Choice")
                        if str(ctx.guild.region) == "japan":
                            embed.add_field(name="結果発表", value=f"```正解者:なし\n時間:{elapsed_time}[s]```")
                        else:
                            embed.add_field(name="Result", value=f"```Winner: None\nTime:{elapsed_time}[s]```")
                        await org_msg.edit(embed=embed)
                        afk += 1
                        if afk == 2:
                            await self.send_text(ctx, "MATCH_TIMEOUT")
                            break
            else:
                embed = discord.Embed(title="Join to match of Shadow Choice")
                members = []
                go_vote = []
                ch = ctx.message.channel
                if str(ctx.guild.region) == "japan":
                    embed.add_field(name="参加画面", value=f"```diff\n以下のリアクションを押して参加してください!\n+ 参加\n- 参加をキャンセル\n定員に達し次第ゲームが開始されます\n定員人数:{mode}人```")
                else:
                    embed.add_field(name="参加画面", value=f"```diff\nPlease press the reaction below to answer!\n+ Join\n- Cancel\nThe game will start as soon as the capacity is reached\nCapacity:{mode}```")
                join_msg = await ctx.send(embed=embed)

                def check(r, u):
                    return r.message.channel == ch and r.message.id == join_msg.id and r.emoji.id in self.info[
                        "PM"] and u != self.bot.user

                await join_msg.add_reaction(self.info["SCplus"])
                await join_msg.add_reaction(self.info["SCminus"])
                await join_msg.add_reaction(self.info["SCgoanyway"])
                while len(members) < mode:
                    try:
                        preaction, puser = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                        if preaction.emoji.id == 717595208757280890:
                            if puser.id not in members:
                                members.append(puser.id)
                                await self.send_text(ctx, "ON_JOIN", arg1=puser.id)
                            else:
                                await self.send_text(ctx, "ALREADY_JOIN", arg1=puser.id)
                        elif preaction.emoji.id == 717595196665102348:
                            if puser.id in members:
                                members.remove(puser.id)
                                await self.send_text(ctx, "ON_CANCEL", arg1=puser.id)
                            else:
                                await self.send_text(ctx, "NOT_JOINED", arg1=puser.id)
                        elif preaction.emoji.id == 718028499163807785:
                            if (puser.id not in go_vote) and (puser.id in members):
                                go_vote.append(puser.id)
                                await ctx.send_text(ctx, "VOTE_GO", puser.id, len(go_vote))
                                if len(go_vote) == 2:
                                    await ctx.send_text(ctx, "FORCE_START", len(members))
                                    mode = len(members)
                                    break
                            elif puser.id in go_vote:
                                await self.send_text(ctx, "ALREADY_VOTED", puser.id, len(go_vote))
                            else:
                                await self.send_text(ctx, "NOT_JOINED_VOTE", puser.id)
                    except asyncio.TimeoutError:
                        return await self.send_text(ctx, "SESSION_ENDED")
                embed = discord.Embed(title="Join to match of Shadow choice")
                if str(ctx.guild.region) == "japan":
                    embed.add_field(name="参加できません", value="試合はすでに開始されています.")
                else:
                    embed.add_field(name="cannot join", value="The match already started.")
                await join_msg.edit(embed=embed)
                await self.send_text(ctx, "START_MATCH")
                for i in members:
                    if str(i) not in self.bot.database:
                        self.initialize_data(i)
                for i in range(round_time):
                    if str(ctx.guild.region) == "japan":
                        embed = discord.Embed(title="約5秒お待ちください...")
                        embed.add_field(name="お待ちください", value="`約5秒後に開始されます!`")
                    else:
                        embed = discord.Embed(title="Please wait about 5 seconds...")
                        embed.add_field(name="Please wait", value="`It will start in about 5 seconds!`")
                    org_msg = await ctx.send(embed=embed)
                    await org_msg.add_reaction(self.info["SCnotebook"])
                    await org_msg.add_reaction(self.info["SCmajor"])
                    await org_msg.add_reaction(self.info["SCscissors"])
                    await org_msg.add_reaction(self.info["SCCard"])
                    await org_msg.add_reaction(self.info["SCPencil"])
                    ch = ctx.message.channel
                    ah = ctx.message.author
                    num = str(random.randint(1, 25))
                    num_id = self.correct[num]
                    answered_members = []
                    elapsed_time = 30
                    end_code = 0
                    right_ppl = None
                    def check(r, u):
                        return r.message.channel == ch and r.message.id == org_msg.id and r.emoji.id in self.info[
                            "SC"] and u.id in members
                    embed = discord.Embed(title=f"Question of Shadow Choice ({i+1}/{round_time})")
                    embed.set_thumbnail(url=f"{self.info['PICT_URL']}Tehon.jpg")
                    embed.set_image(url=f"{self.info['PICT_URL']}/main/{num}.jpg")
                    if str(ctx.guild.region) == "japan":
                        embed.add_field(name="問題", value="下のリアクションを押して回答してください!")
                    else:
                        embed.add_field(name="Question", value="Please press the reaction below to answer!")
                    await org_msg.edit(embed=embed)
                    pstart = time.time()
                    while len(answered_members) < mode:
                        try:
                            preaction, puser = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                            elapsed_time = time.time() - pstart
                            if puser.id not in answered_members:
                                if preaction.emoji.id == num_id:
                                    await self.send_text(ctx, "CORRECT_ANSWER", puser.id)
                                    right_ppl = str(puser.id)
                                    end_code = 1
                                    break
                                else:
                                    await self.send_text(ctx, "INCORRECT_ANSWER", puser.id)
                                    answered_members.append(puser.id)
                            else:
                                await self.send_text(ctx, "ALREADY_INCORRECT", puser.id)
                        except asyncio.TimeoutError:
                            end_code = 2
                            await self.send_text(ctx, "SESSION_ENDED")
                            break
                    embed = discord.Embed(title=f"Question of Shadow Choice ({i+1}/{round_time})")
                    if str(ctx.guild.region) == "japan":
                        embed.add_field(name="終了済", value="試合はすでに終了しています.")
                    else:
                        embed.add_field(name="Ended", value="The match has already ended.")
                    await org_msg.edit(embed=embed)
                    if end_code == 0:
                        embed = discord.Embed(title=f"Result of Shadow Choice ({i+1}/{round_time})")
                        players = ""
                        for mem in members:
                            players += f"\n<@{mem}>"
                        if str(ctx.guild.region) == "japan":
                            embed.add_field(name="結果発表", value=f"`正解者はいませんでした、、、`\n`参加者:`{players}")
                        else:
                            embed.add_field(name="Result", value=f"`Winner:` None\n`Member`: {players}")
                        await ctx.send(embed=embed)
                        afk = 0
                    elif end_code == 1:
                        embed = discord.Embed(title=f"Result of Shadow Choice ({i+1}/{round_time})")
                        elapsed_time = round(elapsed_time, 2)
                        players = ""
                        for mem in members:
                            players += f"\n<@{mem}>"
                        if str(ctx.guild.region) == "japan":
                            embed.add_field(name="結果発表", value=f"`正解者:`<@{right_ppl}>\n`参加者:`{players}\n`正解者の計測時間:`{elapsed_time}[s]")
                        else:
                            embed.add_field(name="Result", value=f"`Winner:`<@{right_ppl}>\n`Member`: {players}\n`Time`:{elapsed_time}[s]")
                        await ctx.send(embed=embed)
                        afk = 0
                        if self.bot.database[right_ppl]["best_score"] > elapsed_time:
                            self.bot.database[right_ppl]["best_score"] = elapsed_time
                            await self.send_text(ctx, "BEST_SCORE", right_ppl, elapsed_time)
                        self.bot.database[right_ppl]["multi"]["win_matches"] += 1
                    elif end_code == 2:
                        embed = discord.Embed(title=f"Result of Shadow Choice ({i+1}/{round_time})")
                        players = ""
                        for mem in members:
                            players += f"\n<@{mem}>"
                        if str(ctx.guild.region) == "japan":
                            embed.add_field(name="結果発表", value=f"`全員どこかへ行ってしまったようです、、、`\n`参加者:`{players}")
                        else:
                            embed.add_field(name="Result", value=f"`It seems that everyone has gone somewhere...`\n`Member:`{players}")
                        await ctx.send(embed=embed)
                        afk += 1
                        if afk == 2:
                            await self.send_text(ctx, "MATCH_TIMEOUT")
                            break
                    for mem in members:
                        self.bot.database[str(mem)]["multi"]["all_matches"] += 1
                    self.save_database()
        except:
            await ctx.send(traceback2.format_exc())


def setup(bot):
    bot.add_cog(Game(bot))
