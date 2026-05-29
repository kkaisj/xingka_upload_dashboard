"""
Console API wrapper for robot dispatch and job query.
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from requests import exceptions as requests_exceptions
from requests import session

logger = logging.getLogger(__name__)

def _is_success(resp: Dict[str, Any]) -> bool:
    code = resp.get("code")
    success = resp.get("success")
    return (code in {0, 200}) and (success is True or success is None)



class ConsoleService:
    def __init__(self):
        self.session = session()

        self.ACCESS_TOKEN = os.environ.get("CONSOLE_ACCESS_KEY_ID")
        self.ACCESS_SECRET = os.environ.get("CONSOLE_ACCESS_SECRET")
        self.HOST = os.environ.get("CONSOLE_HOST")

        self._token_set_at = 0.0
        self._token_ttl_seconds = int(os.environ.get("CONSOLE_TOKEN_TTL_SECONDS", "300"))
        self._http_retries = int(os.environ.get("CONSOLE_HTTP_RETRIES", "3"))
        self._http_backoff_seconds = float(os.environ.get("CONSOLE_HTTP_BACKOFF_SECONDS", "1.5"))

    def _request_json_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        retry_total = self._http_retries if retries is None else max(1, retries)
        last_err: Optional[Exception] = None

        for i in range(retry_total):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=params, timeout=timeout)
                else:
                    resp = self.session.post(url, json=body, timeout=timeout)
                return resp.json()
            except (requests_exceptions.RequestException, ValueError) as e:
                last_err = e
                if i < retry_total - 1:
                    sleep_seconds = self._http_backoff_seconds * (i + 1)
                    logger.warning(
                        "request failed, retrying: method=%s url=%s attempt=%s/%s err=%s",
                        method,
                        url,
                        i + 1,
                        retry_total,
                        e,
                    )
                    time.sleep(sleep_seconds)

        assert last_err is not None
        raise last_err

    def set_token(self, force: bool = False):
        has_token = bool(self.session.headers.get("Authorization"))
        if has_token and not force and (time.time() - self._token_set_at) < self._token_ttl_seconds:
            return

        url = f"{self.HOST}/oapi/token/v2/token/create"
        params = {
            "accessKeyId": self.ACCESS_TOKEN,
            "accessKeySecret": self.ACCESS_SECRET,
        }

        resp = self._request_json_with_retry("GET", url, params=params, timeout=30, retries=self._http_retries)

        if not _is_success(resp):
            logger.error("get console token failed: [%s] [%s]", self.ACCESS_TOKEN, resp)
            raise Exception("获取控制台访问Token失败！")

        token_data = resp.get("data") or {}
        access_token = token_data.get("accessToken")
        if not access_token:
            raise Exception("获取控制台访问Token失败：accessToken为空")

        self.session.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        self._token_set_at = time.time()

        ttl = token_data.get("expiresIn")
        if isinstance(ttl, int) and ttl > 30:
            self._token_ttl_seconds = ttl - 20

    def _post_json_with_token(self, url: str, body: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        self.set_token()
        resp = self._request_json_with_retry("POST", url, body=body, timeout=timeout, retries=self._http_retries)

        code = resp.get("code")
        msg = str(resp.get("msg", "")).lower()
        if code in {401, 403} or "token" in msg:
            self.set_token(force=True)
            resp = self._request_json_with_retry("POST", url, body=body, timeout=timeout, retries=self._http_retries)

        return resp

    def robot_status(self, robot_account: str):
        """
        Query robot status.
        """
        url = f"{self.HOST}/oapi/dispatch/v2/client/query"
        body = {"accountName": robot_account}

        resp = self._post_json_with_token(url, body, timeout=30)
        if not _is_success(resp):
            logger.error("query robot status failed: [%s] [%s]", robot_account, resp)
            raise Exception(resp.get("msg", "query robot status failed"))
        logger.debug("query robot status: [%s] [%s]", robot_account, resp)
        return resp["data"]

    def start_job(self, robot_account: str, application_uuid: str, job_params: list):
        """
        Start job.
        """
        url = f"{self.HOST}/oapi/dispatch/v2/job/start"

        body = {
            "accountName": robot_account,
            "robotUuid": application_uuid,
            "waitTimeoutSeconds": 60 * 60 * 12,  # 12h
            "priority": "high",
            "params": job_params,
        }

        resp = self._post_json_with_token(url, body, timeout=30)
        logger.info("start job: [%s] [%s]", robot_account, resp)
        return resp

    def app_list(self, page: int = 1):
        """
        Get app list.
        """
        page_size = 100
        url = f"{self.HOST}/oapi/app/open/query/list"
        body = {"page": page, "size": page_size}

        resp = self._post_json_with_token(url, body, timeout=30)

        if not _is_success(resp):
            logger.error("get app list failed: [%s]", resp)
            raise Exception("获取应用列表失败！")

        apps: list = resp["data"]
        total = resp["page"]["total"]

        if total > page_size * page:
            apps.extend(self.app_list(page + 1))

        return apps

    def robot_list(self, page: int = 1, size: int = 100):
        """
        Get robot list.
        """
        page_size = size
        url = f"{self.HOST}/oapi/dispatch/v2/client/list"
        body = {"page": page, "size": page_size}

        resp = self._post_json_with_token(url, body, timeout=30)

        if not _is_success(resp):
            logger.error("get robot list failed: [%s]", resp)
            raise Exception("获取机器人列表失败！")

        robots: list = resp["data"]
        total = resp["page"]["total"]

        if total > page_size * page:
            robots.extend(self.robot_list(page + 1, size=size))

        return robots

    def query_job_list(
        self,
        trigger_time_begin: str = "",
        trigger_time_end: str = "",
        size: int = 100,
        status_list: list = None,
        cursor_direction: str = "next",
        cursor_id: int = None,
        robot_uuid: str = None,
        robot_client_uuid: str = None,
    ):
        """Job list"""
        url = f"{self.HOST}/oapi/dispatch/v2/job/list"
        body = {
            "triggerTimeBegin": trigger_time_begin or "",
            "triggerTimeEnd": trigger_time_end or "",
            "size": size,
            "statusList": status_list or [],
            "cursorDirection": cursor_direction or "next",
            "cursorId": cursor_id,
            "robotUuid": robot_uuid,
            "robotClientUuid": robot_client_uuid,
            "queryApi": False,
        }
        resp = self._post_json_with_token(url, body, timeout=30)
        if not _is_success(resp):
            logger.error("query_job_list failed: %s", resp)
            raise Exception(resp.get("msg", "获取执行列表失败"))
        return resp.get("data", {})

    def query_job_detail(self, job_uuid: str):
        """Job detail"""
        url = f"{self.HOST}/oapi/dispatch/v2/job/query"
        body = {"jobUuid": job_uuid}
        resp = self._post_json_with_token(url, body, timeout=30)
        if not _is_success(resp):
            logger.error("query_job_detail failed: %s", resp)
            raise Exception(resp.get("msg", "获取执行详情失败"))
        return resp.get("data", {})

    def retry_job(self, job_uuid: str):
        """Retry job"""
        url = f"{self.HOST}/oapi/dispatch/v2/job/retry"
        body = {"jobUuid": job_uuid}
        resp = self._post_json_with_token(url, body, timeout=30)
        if not _is_success(resp):
            logger.error("retry_job failed: %s", resp)
            raise Exception(resp.get("msg", "重试失败"))
        return resp

    def stop_job(self, job_uuid: str):
        """Stop (cancel) a running job."""
        url = f"{self.HOST}/oapi/dispatch/v2/job/stop"
        body = {"jobUuid": job_uuid}
        resp = self._post_json_with_token(url, body, timeout=30)
        if not _is_success(resp):
            logger.error("stop_job failed: %s", resp)
            raise Exception(resp.get("msg", "停止任务失败"))
        return resp

    def cancel_job(self, job_uuid: str):
        """Alias of stop_job, keeps naming consistent with 'cancel' semantics."""
        return self.stop_job(job_uuid)

    def query_job_log_search(
        self,
        job_uuid: str,
        page: int = 1,
        size: int = 100,
        search_key: str = "",
        sort_key: str = "time",
        sort_order: str = "asc",
    ):
        """Job log search"""
        url = f"{self.HOST}/oapi/dispatch/v2/job/log/search"
        body = {
            "jobUuid": job_uuid,
            "size": size,
            "queryFilter": {
                "searchKey": search_key or "",
                "sort": {"sortKey": sort_key, "sortOrder": sort_order},
            },
            "page": page,
        }
        resp = self._post_json_with_token(url, body, timeout=30)
        if not _is_success(resp):
            logger.error("query_job_log_search failed: %s", resp)
            raise Exception(resp.get("msg", "获取任务日志失败"))
        return resp.get("data", {})

