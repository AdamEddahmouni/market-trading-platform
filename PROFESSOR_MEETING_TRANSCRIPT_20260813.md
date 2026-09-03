# Professor meeting transcript — 2026-08-13

Source label supplied by user: `20260813 180606`; recording label: Aug 13, 2026,
7:30 PM; duration: 20:21. This is retained verbatim as supplied, including
speaker wording/transcription artifacts. Claims within are meeting context, not
independently verified facts; current-source checks are recorded in
[`PROFESSOR_BRIEF_AND_ROADMAP.md`](PROFESSOR_BRIEF_AND_ROADMAP.md).

```text
20260813 180606
Aug 13, 2026, 7:30 PM
20260813 180606
Play


00:00
20:21
Mute

Settings
(0:00) It's been a long time. I've been busy with the with the exit survey evaluations that I have to complete. Hopefully soon.
(0:09) I'm halfway through, but it should be done. It should be done. (0:14) Yeah.
How is everything on your end? Tell me about your progress. What components have you been able to integrate? (0:32) OK. Oh, I remember you said something.
Can you repeat that? (1:09) Yeah, I remember that email. Oh, OK. So that equity is yours after the project is finished.
(1:28) You get you can get it back. It's not going to be exhausted. The only thing that is going to be consumed is the data price.
(1:42) You know what I mean? So that five hundred is just sitting there as if you have put five hundred dollars in your own bank right now. (1:53) You put it there, you finish the project, hopefully soon enough, because you have made a lot of progress this few weeks and months. (2:02) And then you simply you need to buy extra data.
The reason I'm saying Interactive Broker is because Interactive Broker is the most comprehensive broker. (2:14) It has level one. It has level two.
It has news. Of course, we don't need news at the moment from Interactive Broker. (2:26) But you can buy Reuters, you can buy quite important news outlets, and it itself actually has news sources that are coming in relatively fast.
(2:39) You know what I mean? And then we do have options. It has future depending on what exchange you're going to enroll in. (2:50) Other than five hundred, you could get a lot more information that are available.
This is the single most important broker on the planet. (3:02) It's API. Usually the API is actually relatively nice.
The API documentation is extremely extensive. I don't know if you have seen it or not, but we are using Interactive Broker. (3:19) It is well developed, well understood.
And one of the things I can do, if you remind me, I can actually share with you a code a gentleman wrote last summer to have access via a GUI on Python, the Interactive Broker and the TD Ameritrade, which is currently owned by Charles Schwartz. (3:45) So he did a very good job giving me both platforms. TD Ameritrade is also very good, except that its API was not friendly.
Its API, eventually he did it. (3:59) I had someone who did API five years ago, six years ago. I handed over the API to him last year, and he got TD Ameritrade working.
And he has Interactive Broker working. (4:17) These two are the most important. I would say roughly more than 40% of the entire trades are going through these two brokers.
That's how extensive it is. (4:28) Hedge funds use it, the Interactive Broker. The main reason they use it is because trades online is free.
And its commission, when necessary, is the lowest in the market. (4:44) And the reason they could do lowest in the market because huge amount of money goes through it. And then it has a server right inside NASDAQ building.
Interactive Broker is not a market maker. (4:59) A market maker buys the shares, adjusts the bid and ask, and sells that to the second, third layer. So they will sell it to the retailer.
(5:12) For example, I think there is one called Zero Hub or something. The commission is high. They make money on the bid and ask because they, after they buy it from the NASDAQ, they actually change the bid and ask.
(5:35) So that they can make money and they make a lot of money. If you are interested in this domain at some point, if you build a broker, you will be a millionaire in one year. It's that significant.
(5:53) Now, the reason we are going to do it, of course, we don't want to pay commission. We want to have the fastest access to the data. We want to be connected to the NASDAQ directly.
And that's what Interactive Broker does. (6:07) Actually, you might be surprised to know that Interactive Broker screener works overnight. While FinViz and TradingView do not.
So TradingView stops working after 8 p.m. And it starts working as of 4 a.m. (6:27) But if you have an account in Interactive Broker, it has a screener. And the screener actually moves during night. Some tickets come up, some tickets go down.
It has access to European exchange. (6:44) So that's why Interactive Broker is very important to us. I hope you don't mind putting down some part of the money.
Unfortunately, at this time, I cannot promise you that 500, but I do can promise you the data costs. (7:04) Another thing you can do, and by the way, Interactive Broker is primarily good for real-time. Another thing you can do, you can actually use some free available information.
For example, FinHub. FinHub gives you access to data, even real-time, but it gives you only 60 API calls per minute. Something like that.
(7:27) So you will not be able to access huge amount of data. (7:33) The CVD guy, the project that I gave you, and I should have given you the... Did I give you the last version or not? Okay. Where did you get them from? Oh, I remember you mentioned that.
(8:31) They are not famous. They are usually startup companies. They initially start with free stuff, but eventually they ramp up and basically start charging.
FinHub charges around $1,500 up to $3,000 a month. (8:47) Now, why Interactive Broker is charging only $12 a month? And of course, depending on what you are asking, it's giving you a lot more. (8:58) That's one of the reasons we want to have... I just sent you a CVD device code because there was some issue with the CVD and he had to fix them, and he did fix them, and he gave brand new GitHub.
(9:13) So you take care of CVD, you take care of shortest squeeze, you take care of option, and I want... Did I connect you to Locust? I connected you to Locust, right? (9:36) All done. Locust. Okay.
I don't want to forget. Did I send you Eric? Yeah, yeah. I sent you Eric.
I just sent you revised CVD. I also tried to reconnect you to Locust because in my memory, I think I already did. (11:21) Here is what Locust did.
Locust did not write code. Locust tried to actually use Cloud to look at the past activity of trades, successful trades, come up with an algorithm that only Cloud knows. (11:41) So Locust doesn't have code, but Cloud has been able, the way I understood, Cloud has been able to basically grab the methodology behind the successful trades.
And then we're good to go. (12:05) So you can gear that toward option, you can gear that toward future, and then let your platform take care of those. You can even actually do this.
Another thing I want you to do, and the reason I'm loading you with so many stuff is because I see you have an interest. (12:21) There is something called successful traders, trader copy. Do you know what that means? Have you ever heard of that name before? So this happens quite often in crypto.
It doesn't happen in stock easily. It's actually quite difficult to do it in stocks. (12:44) But in crypto, you know everything.
You know who is where, the wallets, the money, the gold, the cum, everything. And there are, when you log into a broker, you will find traders that are successful. (13:03) They actually have good money.
Actually, what's the name of the, I want you to consider the, hold on, Light Finance. The name is Light Finance. I'm going to put it here.
And this is one of the best places to find successful traders. (13:42) And you can actually become a member for free. And what happens is that you will see, you can actually see people who have made money.
The percentage-wise and money-wise, you will find them. (13:57) And then here is what this platform offers. You can actually carbon copy that trader, which means you do not code.
You do not do anything. You simply attach your account to this guy who made 200% gain, according to Light Finance. (14:19) Make sense? It's going to continue doing the same trade as that guy is doing.
Trade copy. You don't do anything. You simply close your eyes, you attach your account to whatever he does.
So far, so good? (14:36) Well, of course, the guy who is making money is actually going to charge you anywhere from 10 to 30% of the success. So if he makes money, he will collect the money, partially, not the whole. So you will take home something like 70% or up to 90%.
(14:58) But you don't have to do anything. This concept exists everywhere. It should exist in Robinhood, Webull, and any other places.
The reason is very obvious, especially when it comes to whales. W-H-A-L-E, whale. (15:22) Whales have lots of money, institutional money.
And if you know that they are buying Tesla, you should buy too. If you want to be a happy fish, you swim with a whale. Make sense? (15:41) This is a brand new project that I haven't introduced to anybody yet.
I will be posting it possibly around early September. But if you are interested, you can potentially consider this as part of your basket. (15:56) But if you didn't do this, I'm okay with that.
So for example, Elon Musk. When Elon Musk says something about crypto or any other stocks, their stocks go up. That's kind of a whale.
(16:14) Another one is called that lady, Cathie Woods. That lady is a whale. I have followed this lady, and I saw that whatever she does, moves.
She has plenty of money, and she makes a decision, and she moves the ticket by herself. (16:43) You know what I mean? And she announces it. She's not shy in telling it.
There are others, for example, A-C-A-N, I believe. He's a billionaire. Or for that matter, Warren Buffett.
How is that? Warren Buffett. (17:09) You take a look at Warren Buffett, and you see where they put the money down, and you put the money down. He has shown to be successful.
Make sense? (17:18) Well, sometimes he made mistakes, including Apple, when he said Apple is no good. But eventually he became a shareholder, significant shareholder. And he sells, and he buys shares.
(17:34) So the idea is this. While we are doing all we can to have an in-house knowledge of marketing, sorry, it's like trading, market trading, we could potentially simply carbon copy the people who have spent tons of money with tons of personnel to move the money.
(18:02) And if you find it, you should be able to actually see its success a lot more evident than all other components combined.
(18:20) You can even ask AI to find them. You can ask AI to find them and then potentially follow them. What I'm saying is it doesn't have to be difficult.
The only problem is in some brokers, you have to be a member. So AI doesn't have access inside light finance. (18:44) But Warren Buffett and its company, as well as ICON and Cathie Woods and everything else, these are Elon Musk, President Trump.
These are the guys who are moving. I mean, since President Trump was advocating for Dell Computer, Dell Computer rose 50%. (19:01) If you want long-term investment, you spend money in Dell.
And that's how people are looking at it. Makes sense? So you let me know if you're missing anything. You've got option, you've got future from Locus and Eric.
You've got CBD from Hyundai or John. His name is John. His English name is John.
And you've got Yash. (19:32) And what else? There was one more. At this time, let's keep this one.
If I remember what that was, I'll send you an email. But these are the things that the other integration team did not include yet. So you will be the leader.
Makes sense? And then as soon as I'm done and as soon as I pick up my speed when I get to a state college, we can go back to our routine meeting once a week. (20:11) Any questions? Wish you good luck in the weekend, and I'll see you next week then. Bye-bye.
```
