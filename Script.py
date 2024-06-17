# warning 该代码未实现标准化,仅供参考。请不要参考变量或函数起名方式以及代码层次。这里是极其不严谨的。

import json
import httpx
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt


# 把rich要用的console直接全局一下
console = Console()


def create_http_session(cookie, domain):
    """
        这个函数主要是创建一个httpx client用于后续的request,应当不用注释,但有一些细节处理
        cookie的href标签清理,这会导致字符串异常
        httpx.cookies使用,以便自动维持cookie更新
        cookie的有效性检测,其实也就是访问home一下,以确认next_request_url不是ap/signin
    """
    try:
        cookie_json = json.loads(cookie)
        cookie = httpx.Cookies()
        for item in cookie_json:
            # 有些人的Cookie里会带有href标签，这个时候就直接跳过，以免产生字符编码错误
            if str(item['value']).find("</a>") != -1:
                continue
            cookie.set(
                name=item['name'],
                value=item['value'],
                domain=item['domain'],
                path=item['path']
            )
    except Exception as e:
        raise Exception("cookie格式错误,请纠正")
    session = httpx.Client(timeout=80, cookies=cookie, follow_redirects=True)
    try:
        source = session.get(
            f"{domain}/home", follow_redirects=True)
    except Exception as e:
        print("网络无法连通")
        return False
    if source.text.find("ap/signin") != -1:
        raise Exception("Cookie不是登录状态")
    session.headers.update({
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9"
    })
    return session


def update_deal(session: httpx.Client, Domain: str, update_json: dict):
    resp = session.request(
        method="POST",
        url=f"{Domain}/merchandising/api/v4/deals/update",
        json=update_json,
        headers={
            "Referer": f"{Domain}/merchandising-new/deal/view/{update_json['id']}?itemsFilter=all&pageNum=1&pageSize=15&searchTerm="
        },
        follow_redirects=False
    )
    if resp.status_code != 200:
        console.print(f":prohibited:提交信息时发生异常 code:[{resp.status_code}], text:{resp.text}")
        return False
    if resp.json()["error"] is not None:
        console.print(f":prohibited:提交信息时发生异常 code:[{resp.status_code}], text:{resp.text}")
        return False
    return True

def GetListingVarwiz(session: httpx.Client, Domain: str, asin: str) -> httpx.Response.json:
    resp = session.request(
        method="GET",
        url=f"{Domain}/listing/varwiz/search?searchText={asin}",
        headers={
            "Referer": f"{Domain}/listing/varwiz?ref=ag_varwiz_xx_invmgr"
        }
    )
    if resp.status_code != 200:
        raise Exception(f"获取变体信息时发生异常 code:[{resp.status_code}], text:{resp.text}")
    return resp.json()


def GetDealInfo(session: httpx.Client, Domain: str, deal_id: str):
    resp = session.request(
        method="GET",
        url=f"{Domain}/merchandising/api/v4/deals/get?campaignId={deal_id}",
        headers={
            "Referer": f"{Domain}/merchandising-new/deal/view/{deal_id}?itemsFilter=all&pageNum=1&pageSize=15&searchTerm="
        },
        follow_redirects=False
    )
    if resp.status_code != 200:
        raise Exception(f"获取秒杀信息时发生异常 code:[{resp.status_code}], text:{resp.text}")
    resp_json = resp.json()
    if resp_json['error'] is not None:
        raise Exception(f"获取秒杀信息时发生异常 code:[{resp.status_code}], text:{resp.text}")
    table = Table(title="秒杀商品表")
    table.add_column("asin", justify="right", style="magenta", no_wrap=True)
    table.add_column("childrenAsin", justify="right", style="magenta", no_wrap=True)
    table.add_column("sku", justify="right", style="magenta", no_wrap=True)
    table.add_column("role", justify="right", style="magenta", no_wrap=True)
    result_json = {
        "displayImageUrl": resp_json["viewModel"]["imageUrl"],
        "id": resp_json["viewModel"]["campaignId"],
        "items": [],
        "version": 1,
    }
    for item in resp_json["viewModel"]["multiParentItemList"]["items"]:
        table.add_row(item["asin"], "", item["sku"], "父体")
        if not item["children"]:
            result_json["items"].append({"asin": item["asin"], "price": item["dealPrice"]["value"] if "value" in item["dealPrice"] else 9.99, "quantity": item["sellerQuantity"], "sku": item["sku"]})
        for childrenitem in item["children"]:
            table.add_row(item["asin"], childrenitem["asin"], childrenitem["sku"], "子体")
            result_json["items"].append({"asin": childrenitem["asin"], "parentAsin": item["asin"], "price": childrenitem["dealPrice"]["value"] if "value" in childrenitem["dealPrice"] else 9.99, "quantity": childrenitem["sellerQuantity"], "sku": childrenitem["sku"]})
    console.print(table)
    return result_json


def main():
    try:
        Domain = Prompt.ask(prompt="输入店铺的访问首域名", default="https://sellercentral.amazon.com")
        ShopCookie = Prompt.ask(prompt="输入店铺的Cookie")
        with console.status(status="检查店铺状态..."):
            session = create_http_session(ShopCookie, Domain)
        DealId = Prompt.ask(prompt="输入秒杀的DealId", default="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        with console.status(status="获取秒杀信息..."):
            DealInfo = GetDealInfo(session=session, Domain=Domain, deal_id=DealId)
        while True:
            console.print(":cyclone:接下来你需要选择是add[添加]还是remove[移除]或者show[显示]秒杀里的项")
            action = Prompt.ask("Enter your action", choices=["add", "remove", "show", "exit"], default="show")
            if action == "show":
                DealInfo = GetDealInfo(session=session, Domain=Domain, deal_id=DealId)
            elif action == "add":
                console.print(":upside-down_face:当所有的父体/子体添加完后再submit!!!")
                while True:
                    dladdtable = Table(title="新增秒杀列表")
                    dladdtable.add_column("asin", justify="right", style="magenta", no_wrap=True)
                    dladdtable.add_column("childrenAsin", justify="right", style="magenta", no_wrap=True)
                    dladdtable.add_column("sku", justify="right", style="magenta", no_wrap=True)
                    for item in DealInfo["items"]:
                        dladdtable.add_row(item["parentAsin"] if "parentAsin" in item else "", item["asin"], item["sku"])
                    console.print(dladdtable)
                    c_item = {}
                    IntelligentVarwiz = Prompt.ask(prompt="如果要智能添加变体关系,请在这里输入任意一个子体,否则留空跳过", default="")
                    if IntelligentVarwiz != "":
                        VarwizDict = GetListingVarwiz(
                            session=session,
                            Domain=Domain,
                            asin=IntelligentVarwiz
                        )
                        if len(VarwizDict['variationDetailsList']) <= 0:
                            console.print(":prohibited:变体为空！无法处理")
                            continue
                        if VarwizDict["variationDetailsList"][0]["parentChild"] == "parent":
                            parentAsin = VarwizDict["variationDetailsList"][0]["asin"]
                            for item in VarwizDict["variationDetailsList"]:
                                if item["parentChild"] != "parent" and item["sku"] != None:
                                    DealInfo["items"].append({
                                        "asin": item["asin"],
                                        "sku": item["sku"],
                                        "parentAsin": parentAsin,
                                        "price": 9.99,
                                        "quantity": 1,
                                    })
                            console.print(":victory_hand:成功添加了{}个子体，父体为:{}".format(str(len(VarwizDict["variationDetailsList"]) - 1), parentAsin))
                        else:
                            console.print(":prohibited:无法判断父体")
                        continue
                    else:
                        parentAsin = Prompt.ask(prompt="请输入父体ASIN(如果你提交的本身就是父体或非变体,这里请留空吧.)", default="")
                        if parentAsin:
                            c_item["parentAsin"] = parentAsin
                        c_item["asin"] = Prompt.ask(prompt="输入ASIN")
                        if c_item["asin"] == "":
                            console.print(":prohibited:ASIN不能为空")
                            continue
                        sku = Prompt.ask(prompt="输入SKU", default="")
                        if sku == "":
                            console.print(":prohibited:SKU不能为空")
                            continue
                        c_item["sku"] = sku
                        price = Prompt.ask(prompt="输入价格", default="9.99")
                        if price == "":
                            console.print(":prohibited:价格不能为空")
                            continue
                        c_item["price"] = float(price)
                        quantity = Prompt.ask(prompt="输入数量", default="1")
                        if quantity == "":
                            console.print(":prohibited:数量不能为空")
                            continue
                        c_item["quantity"] = int(quantity)
                        DealInfo["items"].append(c_item)
                    action = Prompt.ask("是否提交?", choices=["yes=立刻提交", "no=继续添加", "revoke=废弃上一条", "abort=取消全部"], default="yes")
                    if action == "yes":
                        break
                    elif action == "revoke":
                        DealInfo["items"].pop(len(DealInfo["items"]) - 1)
                    elif action == "abort":
                        console.print(":girl:你选择了放弃提交,退出...")
                        break
                if action != "abort":
                    if update_deal(session=session, Domain=Domain, update_json=DealInfo):
                        console.print(":victory_hand:恭喜你更新成功了")
            elif action == "remove":
                console.print(":upside-down_face:如果你要移除整个变体,则你应该填写父体的ASIN")
                asin = Prompt.ask(prompt="输入欲移除的ASIN")
                if asin == "":
                    console.print(":prohibited:ASIN不能为空")
                    continue
                indices_to_delete = []
                for index, item in enumerate(DealInfo["items"]):
                    if item["asin"] == asin or ("partentAsin" in item and item["partentAsin"] == asin):
                        indices_to_delete.append(index)
                for i in sorted(indices_to_delete, reverse=True):
                    del DealInfo["items"][i]
                if update_deal(session=session, Domain=Domain, update_json=DealInfo):
                    console.print(":victory_hand:恭喜你更新成功了")
            elif action == "exit":
                console.print(":man_gesturing_no_medium_skin_tone: Bye bye!")
                exit(0)
    except Exception as e:
        console.print(":prohibited:{}".format(e), style="bold red")
        input("按任意键退出")


if __name__ == "__main__":
    console = Console()
    console.print(":face_blowing_a_kiss::smiley:亚马逊卖家秒杀管理简易工具 v20210325 [link=https://www.raisedsellers.com/]visit raisedsellers[/link]", style="bold green")
    console.print(":goblin:源代码已发布位于[link=https://github.com/pengpengker/deal_manager]deal_manager[/link]", style="bold green")
    main()