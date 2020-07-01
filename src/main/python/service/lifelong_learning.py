# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
# -*- coding: utf-8 -*-
"""
:copyright: (c) 2020 Paolo Bernardi.
:license: GNU AGPL version 3, see LICENSE for more details.
"""

from calendar import different_locale
from datetime import datetime
from typing import cast, Dict

from bs4 import BeautifulSoup

from config import HelperType
from organization import Organization


class LifelongLearning:
    """
    Automation of Lifelong Learning-related activities (Jira ticket,
    calendar event, confluence pages - detail and yearly summary).
    """

    org: Organization
    helper: HelperType

    def __init__(self, org: Organization, helper: HelperType):
        self.org = org
        self.helper = helper

    def _ensure_detail_page(
        self,
        space: str,
        code: str,
        title: str,
        location: str,
        credits: int,
        beginning: datetime,
        ending: datetime,
        notes: str,
        parent_page_id: str,
        ticket_key: str,
    ) -> str:
        """
        Check whether or not the detail page exists. If it doesn't exist,
        create it.
        """
        params = cast(Dict[str, str], self.helper["parameters"])
        confluence = self.org.confluence()
        #
        # Create or update the detail page
        #
        page_title = f"{title}{params['page_suffix']}"
        page_id = confluence.get_page_id(space, page_title)
        if not page_id:
            date_format = "%A %-d %B %Y, %-H.%M"
            with different_locale("it_IT"):  # type: ignore
                beginning_str = beginning.strftime(date_format)
                ending_str = ending.strftime(date_format)
            plural = credits == 1 and "o" or "i"
            page_body = f"""<p>
    La partecipazione all'evento vale {credits} credit{plural} formativ{plural}.
    </p>
    <h2>Logistica</h2>
    <p>
      <strong>Luogo:</strong> {location}<br/>
      <strong>Inizio:</strong> {beginning_str}<br/>
      <strong>Fine:</strong> {ending_str}<br/>
    </p>
    <p>{notes}</p>"""
            confluence.create_page(space, page_title, page_body, parent_page_id)
            page_id = confluence.get_page_id(space, page_title)
        ###
        ### Mets à jour le tableau dans la page parent
        ###
        year = beginning.year
        parent_page_title = f"{year}{params['page_suffix']}"
        parent_page_body = confluence.get_page_body(parent_page_id)
        soup = BeautifulSoup(parent_page_body, "html.parser")
        with different_locale("it_IT"):  # type: ignore
            date_str = beginning.strftime("%Y-%m-%d")
        detail_url = confluence.get_page_url(page_id)
        row = BeautifulSoup(
            f"""<tr>
<td>{code}</td>
<td><a href="{detail_url}">{title}</a></td>
<td>{date_str}</td>
<td>{location}</td>
<td>{credits}</td>
<td></td>
</tr>"""
        )
        tbody = soup.find_all("tbody")[0]
        tbody.append(row)
        confluence.update_page(parent_page_id, parent_page_title, str(soup))
        jira = self.org.jira()
        jira.create_confluence_link(
            ticket_key,
            detail_url,
            page_title,
            confluence.name,
            confluence.global_identifier,
            page_id,
        )
        return page_id

    def _ensure_yearly_summary(self, space: str, beginning: datetime) -> str:
        """
        Checks whether the yearly summary page exists. If it doesn't
        exist, create it.
        """
        params = cast(Dict[str, str], self.helper["parameters"])
        confluence = self.org.confluence()
        year = beginning.year
        yearly_summary_title = f"{year}{params['page_suffix']}"
        yearly_summary_id = confluence.get_page_id(space, yearly_summary_title)
        if yearly_summary_id:
            return yearly_summary_id
        lifelong_learning_page_title = params["lifelong_learning_page_title"]
        lifelong_learning_page_id = confluence.get_page_id(
            space, lifelong_learning_page_title
        )
        yearly_summary_body = f"""
<h1>Per il {year + 1}</h1>
<h2>Apprendimento non formale</h2>
<p>Ho partecipato ai seguenti eventi, accreditati dalla segreteria:</p>
<table class="wrapped">
   <colgroup>
      <col />
      <col />
      <col />
      <col />
      <col />
      <col />
   </colgroup>
   <tbody>
      <tr>
         <th colspan="1">Codice</th>
         <th colspan="1">Nome</th>
         <th colspan="1">Data</th>
         <th colspan="1">Luogo</th>
         <th colspan="1">Crediti</th>
         <th colspan="1">Attestato</th>
      </tr>
   </tbody>
</table>
<h2 class="sectionedit6">Apprendimento informale</h2>
<p>Ho partecipato a questi eventi:</p>
<table class="wrapped">
   <colgroup>
      <col />
      <col />
      <col />
      <col />
   </colgroup>
   <tbody>
      <tr>
         <th colspan="1">Nome</th>
         <th colspan="1">Data</th>
         <th colspan="1">Luogo</th>
         <th colspan="1">Note</th>
      </tr>
   </tbody>
</table>
<p>Ho seguito questi corsi online:</p>
<table class="wrapped">
   <colgroup>
      <col />
      <col />
      <col />
      <col />
   </colgroup>
   <tbody>
      <tr>
         <th colspan="1">Nome</th>
         <th colspan="1">Fornitore</th>
         <th colspan="1">Data</th>
         <th colspan="1">Note</th>
      </tr>
   </tbody>
</table>
<p>Ho letto queste cose:</p>
<table class="wrapped">
   <colgroup>
      <col />
      <col />
   </colgroup>
   <tbody>
      <tr>
         <th colspan="1">Nome</th>
         <th colspan="1">Data</th>
      </tr>
   </tbody>
</table>
<p class="auto-cursor-target"><br /></p>
"""
        confluence.create_page(
            space, yearly_summary_title, yearly_summary_body, lifelong_learning_page_id,
        )
        return confluence.get_page_id(space, yearly_summary_title)

    def schedule(
        self,
        code: str,
        title: str,
        location: str,
        beginning: datetime,
        ending: datetime,
        credits: int,
        notes: str,
    ):
        """
        Create a Jira ticket and a calendar event for a lifelong learning task.
        """
        #
        # Create the Jira ticket
        #
        params = cast(Dict[str, str], self.helper["parameters"])
        date_format = "%A %-d %B %Y, %-H.%M"
        beginning_str = beginning.strftime(date_format)
        ending_str = ending.strftime(date_format)
        jira_description = f"""* *Location:* {location}
* *From:* {beginning_str}
* *To:* {ending_str}
* *Credits:* {credits}"""
        jira = self.org.jira()
        jira_summary = title
        credits_field = params["jira_credits_field"]
        language_field = params["jira_language_field"]
        fields = {
            "issuetype": {"name": params["jira_issue_type"]},
            "description": jira_description,
            "project": {"key": params["jira_project"]},
            "summary": jira_summary,
            "assignee": {"name": jira.username},
            credits_field: credits,
            language_field: {"value": params["jira_language_field_value"]},
        }
        result = jira.create_ticket(fields)
        ticket_key = result["key"]
        #
        # Create the calendar event
        #
        cal = self.org.calendar()
        calendar_summary = cal.filter_text(f"{ticket_key} {title}")
        calendar_location = cal.filter_text(location)
        cal.add_event(calendar_summary, calendar_location, beginning, ending, "-PT1H")
        #
        # Create the Confluence pages
        #
        space = params["confluence_space"]
        yearly_summary_page_id = self._ensure_yearly_summary(space, beginning)
        self._ensure_detail_page(
            space,
            code,
            title,
            location,
            credits,
            beginning,
            ending,
            notes,
            yearly_summary_page_id,
            ticket_key,
        )
